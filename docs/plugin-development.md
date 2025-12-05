# Plugin Development Guide

This guide explains how to create new source plugins for Semantic Weaver.

## Overview

Plugins enable Semantic Weaver to connect to different source systems and extract semantic model definitions. Each plugin must:

1. Connect and authenticate to the source system
2. Extract semantic model metadata (tables, columns, measures, relationships)
3. Convert the extracted data to the Fabric semantic model representation

## Creating a New Plugin

### Step 1: Create the Plugin Folder

Create a new folder under `src/semanticweaver/plugins/` with your source system name:

```
src/semanticweaver/plugins/
├── databricks/
├── looker/          # New plugin
│   ├── __init__.py
│   ├── model.py
│   └── plugin.py
```

### Step 2: Define Configuration Models

In `model.py`, create Pydantic models for your source-specific configuration:

```python
from pydantic import BaseModel, Field
from semanticweaver.models.base import BaseSourceMap

class LookerConfig(BaseModel):
    """Looker-specific configuration."""
    base_url: str = Field(..., description="Looker API base URL")
    client_id: str = Field(..., description="Looker API client ID")
    client_secret: str = Field(..., description="Looker API client secret")

class LookerSourceMap(BaseSourceMap):
    """Configuration model for Looker source."""
    looker: LookerConfig = Field(..., description="Looker configuration")
    
    def get_plugin(self) -> "BaseSourcePlugin":
        from semanticweaver.plugins.looker.plugin import LookerPlugin
        return LookerPlugin(self)
```

### Step 3: Implement the Plugin

In `plugin.py`, extend `BaseSourcePlugin`:

```python
from semanticweaver.plugins.base import BaseSourcePlugin
from semanticweaver.models.intermediate import IntermediateSemanticModel

class LookerPlugin(BaseSourcePlugin):
    async def authenticate(self) -> None:
        # Implement authentication to Looker API
        pass
    
    async def extract_semantic_model(self) -> IntermediateSemanticModel:
        # Extract LookML models and convert to intermediate format
        pass
```

### Step 4: Register the Plugin

Update `semanticweaver/plugins/__init__.py` to export your plugin:

```python
from semanticweaver.plugins.looker import LookerPlugin, LookerSourceMap
```

## Best Practices

1. **Error Handling**: Use specific exception types (ExtractionError, AuthenticationError)
2. **Logging**: Add appropriate logging for debugging
3. **Testing**: Create comprehensive tests in `tests/test_<plugin>_plugin.py`
4. **Documentation**: Document configuration options and requirements
