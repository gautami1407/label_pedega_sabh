from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Optional

class BarcodeScanResponse(BaseModel):
    """Response model for barcode scan endpoint.

    - ``barcode``: the barcode that was submitted
    - ``product_found``: indicates if a product was located in the catalog
    - ``source``: optional string describing the data source (e.g. "local", "off", "usda")
    - ``product``: raw product document when found (may be empty dict if not found)
    """
    barcode: str = Field(..., description="Submitted barcode value")
    product_found: bool = Field(..., description="True when a product was found")
    source: Optional[str] = Field(None, description="Data source identifier")
    product: dict[str, Any] = Field(default_factory=dict, description="Product payload when found")
