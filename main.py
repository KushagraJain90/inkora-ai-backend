
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.core.gemini import client
from app.routers.conversion import router as conversion_router
from app.routers.evaluation import router as evaluation_router
from app.routers.ocr import router as ocr_router

app = FastAPI(
    title="Inkora AI OCR API",
    version="1.0.0",
)


# Register API routers
app.include_router(evaluation_router)
app.include_router(ocr_router)
app.include_router(conversion_router)


# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
        openapi_version="3.0.3",
    )

    def fix_binary_file_fields(node):
        """Convert binary upload schemas to OpenAPI 3.0 format."""
        if isinstance(node, dict):
            if node.get("contentMediaType") == "application/octet-stream":
                node.pop("contentMediaType", None)
                node["format"] = "binary"

            for value in node.values():
                fix_binary_file_fields(value)

        elif isinstance(node, list):
            for item in node:
                fix_binary_file_fields(item)

    fix_binary_file_fields(schema)

    # Correct evaluation endpoint upload fields
    components = schema.get("components", {}).get("schemas", {})

    for component in components.values():
        properties = component.get("properties", {})

        if "question_image" in properties:
            properties["question_image"] = {
                "type": "string",
                "format": "binary",
            }

        if "student_answer_images" in properties:
            properties["student_answer_images"] = {
                "type": "array",
                "items": {
                    "type": "string",
                    "format": "binary",
                },
            }

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


# Health check
@app.get("/health")
def health():
    return {
        "status": "ok",
        "api_key_configured": client is not None,
    }
