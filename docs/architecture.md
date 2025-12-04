# Semantic Weaver Architecture

## Overview

Semantic Weaver follows a plugin-based architecture that enables migration of semantic models from various source systems to Microsoft Fabric.

## Components

### Core Components

1. **WeaverAgent** (`src/semanticweaver/weaver.py`)
   - Main entry point and orchestrator
   - Coordinates the migration process

2. **AuthenticationManager** (`src/semanticweaver/core/auth.py`)
   - Handles authentication to source and target systems
   - Supports Azure Service Principal authentication

3. **SemanticModelTransformer** (`src/semanticweaver/core/transformer.py`)
   - Transforms source-specific models to intermediate format
   - Converts intermediate format to Fabric semantic model

4. **FabricClient** (`src/semanticweaver/core/api/fabric_client.py`)
   - REST API client for Microsoft Fabric
   - Creates and manages semantic models in Fabric workspaces

### Models

1. **Base Models** (`src/semanticweaver/models/base.py`)
   - Configuration models shared across all plugins
   - FabricConfig, ServicePrincipalConfig, SourceConfig

2. **Intermediate Models** (`src/semanticweaver/models/intermediate.py`)
   - Generic semantic model representation
   - Tables, columns, measures, relationships

3. **Fabric Models** (`src/semanticweaver/models/fabric.py`)
   - Power BI semantic model format
   - TMSL/TMDL compatible structures

### Plugins

Each plugin folder contains:
- `model.py` - Source-specific configuration and data models
- `plugin.py` - Plugin implementation extending BaseSourcePlugin

## Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Source System  │ ──► │  Intermediate    │ ──► │  Fabric         │
│  (Databricks)   │     │  Representation  │     │  Semantic Model │
└─────────────────┘     └──────────────────┘     └─────────────────┘
       │                        │                        │
       ▼                        ▼                        ▼
   Plugin.extract()    Transformer.transform()   FabricClient.deploy()
```

## Extension Points

1. **New Source Plugins**: Add new folders under `src/semanticweaver/plugins/`
2. **Custom Transformations**: Extend SemanticModelTransformer
3. **Additional Fabric Features**: Extend FabricClient
