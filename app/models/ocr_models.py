
from typing import Literal

from pydantic import BaseModel, Field


class VisualRegion(BaseModel):
    region_type: str
    description: str
    x_min: float = Field(ge=0, le=1)
    y_min: float = Field(ge=0, le=1)
    x_max: float = Field(ge=0, le=1)
    y_max: float = Field(ge=0, le=1)


class PageTranscription(BaseModel):
    page_number: int = Field(ge=1)
    transcription: str
    visual_regions: list[VisualRegion] = Field(default_factory=list)


class OcrBatchResponse(BaseModel):
    pages: list[PageTranscription]


class ConversionVisualRegion(BaseModel):
    region_id: str = Field(
        min_length=1,
        description="Unique ID, such as EQ1 or DIAG1"
    )

    region_type: Literal["equation", "diagram"]
    description: str

    # Coordinates are normalized to the original image.
    x_min: float = Field(ge=0, le=1)
    y_min: float = Field(ge=0, le=1)
    x_max: float = Field(ge=0, le=1)
    y_max: float = Field(ge=0, le=1)


class ConversionPageTranscription(BaseModel):
    page_number: int = Field(ge=1)
    transcription: str
    visual_regions: list[ConversionVisualRegion] = Field(
        default_factory=list
    )


class ConversionBatchResponse(BaseModel):
    pages: list[ConversionPageTranscription]
