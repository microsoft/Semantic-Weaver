# Semantic Weaver: Migrate semantic models to Microsoft Fabric

</p>
<p align="center">
<a href="https://badgen.net/github/license/microsoft/Semantic-Weaver" target="_blank">
    <img src="https://badgen.net/github/license/microsoft/Semantic-Weaver" alt="License">
</a>
<a href="https://badgen.net/github/releases/microsoft/Semantic-Weaver" target="_blank">
    <img src="https://badgen.net/github/releases/microsoft/Semantic-Weaver" alt="Test">
</a>
<a href="https://badgen.net/github/contributors/microsoft/Semantic-Weaver" target="_blank">
    <img src="https://badgen.net/github/contributors/microsoft/Semantic-Weaver" alt="Publish">
</a>
<a href="https://badgen.net/github/commits/microsoft/Semantic-Weaver" target="_blank">
    <img src="https://badgen.net/github/commits/microsoft/Semantic-Weaver" alt="Commits">
</a>
<a href="https://badgen.net/pypi/v/Semantic-Weaver" target="_blank">
    <img src="https://badgen.net/pypi/v/Semantic-Weaver" alt="Package version">
</a>
  <a href="https://badgen.net/pypi/dm/Semantic-Weaver" target="_blank">
    <img src="https://badgen.net/pypi/dm/Semantic-Weaver" alt="Monthly Downloads">
</a>
</a>
  <a href="https://badge.socket.dev/pypi/package/Semantic-Weaver?artifact_id=tar-gz" target="_blank">
    <img src="https://badge.socket.dev/pypi/package/Semantic-Weaver?artifact_id=tar-gz" alt="Socket Badge">
</a>
</p>

## Introduction

Semantic Weaver is a Python library designed to migrate semantic model definitions from systems like Databricks (using Databricks Metric Views), Looker, and others into Microsoft Fabric Semantic Models.

The library achieves this by:
1. **Reading** the source system semantic model definition
2. **Creating** an intermediate generic representation
3. **Deploying** a proper Power BI Semantic Model to a Microsoft Fabric Workspace

Semantic Weaver features a plugin architecture, allowing contributors to easily add support for new source systems.

## 🚀 Features

- **Microsoft Fabric Integration**: Direct deployment of semantic models to Fabric Workspaces
- **Multiple Source Systems**: Support for Databricks Metric Views with more connectors planned
- **Plugin Architecture**: Extensible framework allowing easy addition of new source systems
- **Intermediate Representation**: Generic semantic model format enabling cross-platform migrations
- **Runs Anywhere**: Execute from Fabric Notebooks or any Python runtime environment

## Project Structure

```
.github/            # GitHub workflows and configurations
assets/             # Project assets and images
docs/               # Documentation
src/
└── semanticweaver/
    ├── core/           # Core functionality
    │   └── api/        # REST API calls for Fabric deployment
    ├── models/         # Pydantic models for semantic representations
    ├── plugins/        # Source system plugins
    │   └── databricks/ # Databricks Metric Views connector
    └── weaver.py       # Main entry point
tests/              # Unit and integration tests
```

## Table of Contents

- [Installation](#️-installation)
- [Getting Started](#-getting-started)
  - [General Prerequisites](#-general-prerequisites)
  - [Databricks Specific Setup](#-databricks-specific-setup)
  - [Running the Weaver](#-running-the-weaver)
- [Configuration](#-configuration)
- [Contributing](#-contributing)
- [License](#-license)

## 🛠️ Installation

Make sure your Python version is greater or equal than 3.11. Then, install the library:

```bash
pip install semantic-weaver
```

## 🚀 Getting Started

Follow the General Prerequisites and Installation steps below. Then, depending on your source system, follow the specific setup instructions for Databricks (or other supported sources as they become available).

### 📋 General Prerequisites

Before installing and running this solution, ensure you have:

- **Azure Service Principal** with the following permissions:
  - Access to the target Microsoft Fabric Workspace
  - Ability to create and modify Semantic Models in Fabric
  
- **A client secret** for the Service Principal ([Create a client secret](https://learn.microsoft.com/en-us/entra/identity-platform/howto-create-service-principal-portal#option-3-create-a-new-client-secret))

- **Fabric Workspace Access**: The Service Principal must be added as **Admin** on the Fabric Workspace where the semantic model will be deployed ([Give access to workspaces](https://learn.microsoft.com/en-us/fabric/fundamentals/give-access-workspaces))

- **Fabric API Access**: The Service Principal needs to be able to call public Fabric REST APIs. Configure this in tenant settings via [service-principals-can-call-fabric-public-apis](https://learn.microsoft.com/en-us/fabric/admin/service-admin-portal-developer#service-principals-can-call-fabric-public-apis)

> 📌 **Note**: Each source system may have additional prerequisites. See the source-specific setup sections below.

### 🧵 Databricks Specific Setup

#### Azure Databricks Configuration

We assume you have an Azure Databricks workspace with Unity Catalog enabled and Metric Views defined.

To allow Semantic Weaver to read the Unity Catalog metadata and metric view definitions, you need to configure appropriate access for your Azure Service Principal:

1. Go to the Account Admin Console ([https://accounts.azuredatabricks.net/](https://accounts.azuredatabricks.net/)) ➡️ User Management ➡️ Add your Azure Service Principal
2. Grant the Service Principal access to read the Unity Catalog metadata
3. Ensure the Service Principal can access the Metric Views you want to migrate

#### Update your Configuration file

Create a `config.yaml` file based on your environment. The configuration specifies the source system, target Fabric workspace, connectivity settings, and additional options.

Example configuration:

```yaml
# Fabric target configuration
fabric:
  workspace_id: your-fabric-workspace-id
  tenant_id: your-tenant-id

# Service Principal credentials
service_principal:
  client_id: your-client-id
  client_secret: your-client-secret
  tenant_id: your-tenant-id

# Source system configuration
source:
  name: your-databricks-catalog
  type: DATABRICKS

# Databricks-specific settings
databricks:
  workspace_url: https://adb-xxxxxxxxxx.azuredatabricks.net/
  account_id: your-databricks-account-id
  account_api_token: your-databricks-api-token
```

### ▶️ Running the Weaver

This is all the code you need. Just make sure Semantic Weaver can access your YAML configuration file.

```python
# Import the SemanticWeaver library
from semanticweaver.weaver import WeaverAgent
from semanticweaver.plugins.databricks.model import DatabricksSourceMap

# Load config
config = DatabricksSourceMap.from_yaml("path_to_your_config.yaml")

# Run the SemanticWeaver
await WeaverAgent.run(config)
```

All done! You can now check your Microsoft Fabric Workspace for the newly created Semantic Model.

## 📚 Configuration

The `config.yaml` file drives the entire migration process. Here are the main configuration sections:

| Section | Description |
|---------|-------------|
| `fabric` | Target Fabric workspace settings (workspace_id, tenant_id) |
| `service_principal` | Azure Service Principal credentials for authentication |
| `source` | Source system name and type |
| `databricks` | Databricks-specific connection settings |

## 🙋 Contributing

This project welcomes contributions and suggestions. Most contributions require you to agree to a Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us the rights to use your contribution. For details, visit [https://cla.opensource.microsoft.com](https://cla.opensource.microsoft.com/).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

### Adding New Source Plugins

The plugin architecture makes it easy to add support for new source systems:

1. Create a new folder under `semanticweaver/plugins/` for your source system
2. Implement the required interfaces to:
   - Connect to the source system
   - Extract semantic model definitions
   - Convert to the intermediate representation
3. Add corresponding Pydantic models in `semanticweaver/models/`
4. Submit a pull request!

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🛡️ Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.
