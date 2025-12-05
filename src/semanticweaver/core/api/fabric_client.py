"""
Microsoft Fabric REST API client.

This module provides functionality to interact with Microsoft Fabric APIs
for creating and managing Power BI Semantic Models using Service Principal
authentication.
"""

import asyncio
import base64
import logging
from typing import Any

import httpx
from azure.identity import ClientSecretCredential

from semanticweaver.models.base import ServicePrincipalConfig
from semanticweaver.models.fabric import FabricSemanticModel

logger = logging.getLogger(__name__)


class DeploymentError(Exception):
    """Raised when deployment to Fabric fails."""

    pass


class FabricAuthenticationError(Exception):
    """Raised when authentication to Fabric fails."""

    pass


class FabricClient:
    """
    Client for Microsoft Fabric REST APIs.

    Handles:
    - Authenticating to Fabric using Service Principal
    - Creating semantic models in Fabric workspaces
    - Updating existing semantic models with TMDL definitions
    - Managing semantic model lifecycle
    
    The client uses the Fabric REST API v1 to deploy semantic models.
    Authentication is performed using Azure AD Service Principal credentials.
    """

    FABRIC_API_BASE_URL = "https://api.fabric.microsoft.com/v1"
    FABRIC_API_SCOPE = "https://api.fabric.microsoft.com/.default"

    def __init__(
        self,
        workspace_id: str,
        service_principal: ServicePrincipalConfig,
    ):
        """
        Initialize the Fabric client.

        Args:
            workspace_id: The target Fabric workspace ID (GUID).
            service_principal: Service Principal credentials for authentication.
        """
        self.workspace_id = workspace_id
        self._service_principal = service_principal
        self._credential: ClientSecretCredential | None = None
        self._access_token: str | None = None
        self._http_client: httpx.AsyncClient | None = None

    async def authenticate(self) -> None:
        """
        Authenticate to Microsoft Fabric using Service Principal credentials.

        Uses the Azure Identity library to obtain an access token for Fabric APIs.

        Raises:
            FabricAuthenticationError: If authentication fails.
        """
        try:
            logger.info("Authenticating to Microsoft Fabric...")
            
            self._credential = ClientSecretCredential(
                tenant_id=self._service_principal.tenant_id,
                client_id=self._service_principal.client_id,
                client_secret=self._service_principal.client_secret,
            )
            
            # Get access token for Fabric API
            token = self._credential.get_token(self.FABRIC_API_SCOPE)
            self._access_token = token.token
            
            # Initialize HTTP client
            self._http_client = httpx.AsyncClient(
                base_url=self.FABRIC_API_BASE_URL,
                headers=self._get_headers(),
                timeout=60.0,
            )
            
            logger.info("Successfully authenticated to Microsoft Fabric")
            
        except Exception as e:
            raise FabricAuthenticationError(
                f"Failed to authenticate to Fabric: {e}"
            ) from e

    async def close(self) -> None:
        """Close the HTTP client and clean up resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self) -> "FabricClient":
        """Async context manager entry."""
        await self.authenticate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers with authentication."""
        if not self._access_token:
            raise FabricAuthenticationError(
                "Not authenticated. Call authenticate() first."
            )
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def _ensure_authenticated(self) -> None:
        """Ensure the client is authenticated."""
        if not self._http_client or not self._access_token:
            raise FabricAuthenticationError(
                "Not authenticated. Call authenticate() first."
            )

    async def deploy_semantic_model(self, model: FabricSemanticModel) -> str:
        """
        Deploy a semantic model to Microsoft Fabric.

        This method handles the full deployment workflow:
        1. Check if the model already exists (by name)
        2. Create a new model or update the existing one
        3. Upload the TMDL definition

        Args:
            model: The Fabric semantic model to deploy.

        Returns:
            str: The ID of the created/updated semantic model in Fabric.

        Raises:
            DeploymentError: If deployment fails.
        """
        self._ensure_authenticated()
        
        try:
            # Check if model already exists
            existing_model = await self.find_semantic_model_by_name(model.name)
            
            if existing_model:
                logger.info(f"Updating existing semantic model: {model.name}")
                model_id = existing_model["id"]
                await self.update_semantic_model_definition(model_id, model)
            else:
                logger.info(f"Creating new semantic model: {model.name}")
                model_id = await self.create_semantic_model(model)
            
            return model_id
            
        except Exception as e:
            raise DeploymentError(
                f"Failed to deploy semantic model '{model.name}': {e}"
            ) from e

    async def deploy_semantic_models(
        self, models: list[FabricSemanticModel]
    ) -> list[str]:
        """
        Deploy multiple semantic models to Microsoft Fabric.

        Args:
            models: List of Fabric semantic models to deploy.

        Returns:
            list[str]: List of IDs for each created/updated semantic model.

        Raises:
            DeploymentError: If deployment of any model fails.
        """
        deployed_ids = []
        for model in models:
            model_id = await self.deploy_semantic_model(model)
            deployed_ids.append(model_id)
        return deployed_ids

    async def create_semantic_model(self, model: FabricSemanticModel) -> str:
        """
        Create a new semantic model in the workspace.

        Creates the semantic model with the TMDL definition included.

        Args:
            model: The Fabric semantic model definition.

        Returns:
            str: The ID of the created semantic model.

        Raises:
            DeploymentError: If creation fails.
        """
        self._ensure_authenticated()
        
        # Generate TMDL definition
        tmdl_files = model.to_tmdl()
        
        # Convert TMDL to the format expected by the API
        definition_parts = []
        for path, content in tmdl_files.items():
            # Encode content as base64
            encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
            definition_parts.append({
                "path": path,
                "payload": encoded_content,
                "payloadType": "InlineBase64",
            })
        
        # Create the semantic model with definition included
        create_payload = {
            "displayName": model.name,
            "description": model.description or "Semantic model created by Semantic Weaver",
            "definition": {
                "parts": definition_parts,
            }
        }
        
        logger.debug(f"Creating semantic model with payload: {create_payload}")
        
        response = await self._http_client.post(
            f"/workspaces/{self.workspace_id}/semanticModels",
            json=create_payload,
        )
        
        if response.status_code not in (200, 201, 202):
            error_detail = self._extract_error(response)
            raise DeploymentError(
                f"Failed to create semantic model '{model.name}': {response.status_code} - {error_detail}"
            )
        
        # Handle 202 Accepted - may be async operation
        if response.status_code == 202:
            # Check for Location header for long-running operation
            location = response.headers.get("Location")
            operation_id = response.headers.get("x-ms-operation-id")
            logger.debug(f"Received 202 Accepted. Location: {location}, Operation ID: {operation_id}")
            
            # Try to get response body, it might be empty for 202
            try:
                result = response.json()
                logger.debug(f"Response body: {result}")
            except Exception:
                result = None
            
            # If we have an ID in the response, use it
            if result and "id" in result:
                model_id = result["id"]
                logger.info(f"Created semantic model with ID: {model_id}")
                return model_id
            
            # For 202 with no ID, we need to wait for the operation to complete
            # and then find the model by name
            if location:
                await self._wait_for_operation(location)
            
            # Find the model by name
            found_model = await self.find_semantic_model_by_name(model.name)
            if found_model:
                logger.info(f"Created semantic model with ID: {found_model['id']}")
                return found_model["id"]
            
            raise DeploymentError(
                f"Created semantic model '{model.name}' but could not retrieve its ID"
            )
        
        result = response.json()
        model_id = result["id"]
        logger.info(f"Created semantic model with ID: {model_id}")
        
        return model_id
    
    async def _wait_for_operation(self, location: str, timeout_seconds: int = 300) -> None:
        """
        Wait for a long-running operation to complete.
        
        Args:
            location: The URL to poll for operation status.
            timeout_seconds: Maximum time to wait for completion.
            
        Raises:
            DeploymentError: If the operation fails or times out.
        """
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            response = await self._http_client.get(location)
            
            if response.status_code == 200:
                # Operation complete
                result = response.json()
                status = result.get("status", "").lower()
                
                if status in ("succeeded", "completed"):
                    logger.debug("Long-running operation completed successfully")
                    return
                elif status in ("failed", "cancelled"):
                    error = result.get("error", {}).get("message", "Unknown error")
                    raise DeploymentError(f"Operation failed: {error}")
                
            elif response.status_code == 202:
                # Still in progress
                pass
            else:
                logger.warning(f"Unexpected status while polling: {response.status_code}")
            
            # Wait before polling again
            await asyncio.sleep(2)
        
        raise DeploymentError(f"Operation timed out after {timeout_seconds} seconds")

    async def update_semantic_model_definition(
        self, model_id: str, model: FabricSemanticModel
    ) -> None:
        """
        Update the definition of an existing semantic model using TMDL.

        Args:
            model_id: The ID of the semantic model to update.
            model: The Fabric semantic model with the new definition.

        Raises:
            DeploymentError: If update fails.
        """
        self._ensure_authenticated()
        
        # Generate TMDL definition
        tmdl_files = model.to_tmdl()
        
        # Convert TMDL to the format expected by the API
        # The API expects a definition with parts array
        definition_parts = []
        for path, content in tmdl_files.items():
            # Encode content as base64
            encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
            definition_parts.append({
                "path": path,
                "payload": encoded_content,
                "payloadType": "InlineBase64",
            })
        
        update_payload = {
            "definition": {
                "parts": definition_parts,
            }
        }
        
        response = await self._http_client.post(
            f"/workspaces/{self.workspace_id}/semanticModels/{model_id}/updateDefinition",
            json=update_payload,
        )
        
        if response.status_code not in (200, 202):
            error_detail = self._extract_error(response)
            raise DeploymentError(
                f"Failed to update semantic model definition: {response.status_code} - {error_detail}"
            )
        
        logger.info(f"Updated semantic model definition for ID: {model_id}")

    async def get_semantic_model(self, model_id: str) -> dict[str, Any] | None:
        """
        Get details of an existing semantic model.

        Args:
            model_id: The ID of the semantic model.

        Returns:
            The semantic model details if found, None if not found.

        Raises:
            DeploymentError: If the request fails (other than 404).
        """
        self._ensure_authenticated()
        
        response = await self._http_client.get(
            f"/workspaces/{self.workspace_id}/semanticModels/{model_id}"
        )
        
        if response.status_code == 404:
            return None
        
        if response.status_code != 200:
            error_detail = self._extract_error(response)
            raise DeploymentError(
                f"Failed to get semantic model: {response.status_code} - {error_detail}"
            )
        
        return response.json()

    async def find_semantic_model_by_name(self, name: str) -> dict[str, Any] | None:
        """
        Find a semantic model by its display name.

        Args:
            name: The display name of the semantic model.

        Returns:
            The semantic model details if found, None otherwise.
        """
        models = await self.list_semantic_models()
        for model in models:
            if model.get("displayName") == name:
                return model
        return None

    async def list_semantic_models(self) -> list[dict[str, Any]]:
        """
        List all semantic models in the workspace.

        Returns:
            List of semantic model summaries.

        Raises:
            DeploymentError: If the request fails.
        """
        self._ensure_authenticated()
        
        response = await self._http_client.get(
            f"/workspaces/{self.workspace_id}/semanticModels"
        )
        
        if response.status_code != 200:
            error_detail = self._extract_error(response)
            raise DeploymentError(
                f"Failed to list semantic models: {response.status_code} - {error_detail}"
            )
        
        result = response.json()
        return result.get("value", [])

    async def delete_semantic_model(self, model_id: str) -> None:
        """
        Delete a semantic model from the workspace.

        Args:
            model_id: The ID of the semantic model to delete.

        Raises:
            DeploymentError: If deletion fails.
        """
        self._ensure_authenticated()
        
        response = await self._http_client.delete(
            f"/workspaces/{self.workspace_id}/semanticModels/{model_id}"
        )
        
        if response.status_code not in (200, 204):
            error_detail = self._extract_error(response)
            raise DeploymentError(
                f"Failed to delete semantic model: {response.status_code} - {error_detail}"
            )
        
        logger.info(f"Deleted semantic model with ID: {model_id}")

    async def get_semantic_model_definition(self, model_id: str) -> dict[str, str]:
        """
        Get the TMDL definition of a semantic model.

        Args:
            model_id: The ID of the semantic model.

        Returns:
            Dictionary mapping file paths to their TMDL content.

        Raises:
            DeploymentError: If the request fails.
        """
        self._ensure_authenticated()
        
        response = await self._http_client.post(
            f"/workspaces/{self.workspace_id}/semanticModels/{model_id}/getDefinition",
            json={"format": "TMDL"},
        )
        
        if response.status_code not in (200, 202):
            error_detail = self._extract_error(response)
            raise DeploymentError(
                f"Failed to get semantic model definition: {response.status_code} - {error_detail}"
            )
        
        result = response.json()
        tmdl_files = {}
        
        for part in result.get("definition", {}).get("parts", []):
            path = part.get("path", "")
            payload = part.get("payload", "")
            payload_type = part.get("payloadType", "")
            
            if payload_type == "InlineBase64":
                content = base64.b64decode(payload).decode("utf-8")
            else:
                content = payload
            
            tmdl_files[path] = content
        
        return tmdl_files

    def _extract_error(self, response: httpx.Response) -> str:
        """Extract error message from response."""
        try:
            error_data = response.json()
            if "error" in error_data:
                return error_data["error"].get("message", str(error_data))
            return str(error_data)
        except Exception:
            return response.text or "Unknown error"
