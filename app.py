from fastapi import FastAPI
from mcp.server.sse import SseServerTransport
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount, Route
import uvicorn
from mcp_image import mcp  # Import the FastMCP instance from mcp_image

#Defining some end points to test

app = FastAPI(title="Image MCP Server API")

@app.get("/")
async def root():
    return {"message": "Image MCP Server is running", "tools": ["search_google_images", "save_images_to_azure", "upload_single_image_to_azure", "download_image_from_azure"]}   

@app.get("/health")
async def health():
    return {"status": "ok"} 



##############################################

# Using the mcp instance from mcp_image.py which contains all the image tools


def create_sse_server(mcp: FastMCP):
    """Create a Starlette app that handles SSE connections and message handling"""
    transport = SseServerTransport("/messages/")

    # Define handler functions
    async def handle_sse(request):
        async with transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp._mcp_server.run(
                streams[0], streams[1], mcp._mcp_server.create_initialization_options()
            )

    # Create Starlette routes for SSE and message handling
    routes = [
        Route("/sse/", endpoint=handle_sse),
        Mount("/messages/", app=transport.handle_post_message),
    ]

    # Create a Starlette app
    return Starlette(routes=routes)


app.mount("/", create_sse_server(mcp))

###########################################################################

# Image tools are defined in mcp_image.py and include:
# - search_google_images: Search for images on Google Images
# - save_images_to_azure: Save found images to Azure Blob Storage  
# - upload_single_image_to_azure: Upload a single image to Azure
# - download_image_from_azure: Download an image from Azure Blob Storage


# For local testing and Azure deployment
if __name__ == "__main__":   
    # Use 0.0.0.0 for Azure deployment, port from environment variable or default to 8000
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=port)