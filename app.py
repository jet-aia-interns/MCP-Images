# from fastapi import FastAPI
# from mcp.server.sse import SseServerTransport
# from mcp.server.fastmcp import FastMCP
# from starlette.applications import Starlette
# from starlette.routing import Mount, Route
# import uvicorn
# from mcp_image import mcp  # Import the FastMCP instance from mcp_image

# #Defining some end points to test
# from fastapi.middleware.cors import CORSMiddleware

# app = FastAPI(title="Image MCP Server API")

 
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # or ["https://claude.ai"]
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# @app.get("/mcp/manifest.json")
# async def manifest():
#     return {
#         "name": "image-mcp-server",
#         "description": "Provides image search, upload, and download tools",
#         "version": "1.0.0",
#         "tools": [
#             {"name": "search_google_images", "description": "Search for images on Google"},
#             {"name": "save_images_to_azure", "description": "Save found images to Azure Blob Storage"},
#             {"name": "upload_single_image_to_azure", "description": "Upload a single image to Azure Blob Storage"},
#             {"name": "download_image_from_azure", "description": "Download an image from Azure Blob Storage"}
#         ],
#         "auth": {"type": "none"},
#         "endpoints": {
#             "sse": "https://image-mcp-server-fhf0bzdxdnced7fj.australiaeast-01.azurewebsites.net/mcp/sse/"
#         }
#     }


# @app.get("/")
# async def root():
#     return {"message": "Image MCP Server is running", "tools": ["search_google_images", "save_images_to_azure", "upload_single_image_to_azure", "download_image_from_azure"]}   

# @app.get("/health")
# async def health():
#     return {"status": "ok"} 



# ##############################################

# # Using the mcp instance from mcp_image.py which contains all the image tools


# def create_sse_server(mcp: FastMCP):
#     """Create a Starlette app that handles SSE connections and message handling"""
#     transport = SseServerTransport("/messages/")

#     # Define handler functions
#     async def handle_sse(request):
#         async with transport.connect_sse(
#             request.scope, request.receive, request._send
#         ) as streams:
#             await mcp._mcp_server.run(
#                 streams[0], streams[1], mcp._mcp_server.create_initialization_options()
#             )

#     # Create Starlette routes for SSE and message handling
#     routes = [
#         Route("/sse/", endpoint=handle_sse),
#         Mount("/messages/", app=transport.handle_post_message),
#     ]

#     # Create a Starlette app
#     return Starlette(routes=routes)


# app.mount("/", create_sse_server(mcp))

# ###########################################################################

# # Image tools are defined in mcp_image.py and include:
# # - search_google_images: Search for images on Google Images
# # - save_images_to_azure: Save found images to Azure Blob Storage  
# # - upload_single_image_to_azure: Upload a single image to Azure
# # - download_image_from_azure: Download an image from Azure Blob Storage


# # For local testing and Azure deployment
# if __name__ == "__main__":   
#     # Use 0.0.0.0 for Azure deployment, port from environment variable or default to 8000
#     import os
#     port = int(os.environ.get("PORT", 8000))
#     uvicorn.run(app, host="0.0.0.0", port=port)
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.sse import SseServerTransport
import uvicorn
import os

# Import your MCP instance
try:
    from mcp_image import mcp
except ImportError:
    # Fallback if mcp_image import fails
    mcp = None
    print("Warning: Could not import mcp_image module")

app = FastAPI(title="Image MCP Server API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "Image MCP Server is running", 
        "status": "healthy",
        "tools": ["search_google_images", "save_images_to_azure", "upload_single_image_to_azure", "download_image_from_azure"]
    }

@app.get("/health")
async def health():
    return {"status": "ok", "service": "image-mcp-server"}

@app.get("/mcp/manifest.json")
async def manifest():
    return {
        "name": "image-mcp-server",
        "description": "Provides image search, upload, and download tools",
        "version": "1.0.0",
        "tools": [
            {"name": "search_google_images", "description": "Search for images on Google"},
            {"name": "save_images_to_azure", "description": "Save found images to Azure Blob Storage"},
            {"name": "upload_single_image_to_azure", "description": "Upload a single image to Azure Blob Storage"},
            {"name": "download_image_from_azure", "description": "Download an image from Azure Blob Storage"}
        ],
        "auth": {"type": "none"},
        "endpoints": {
            "sse": "https://image-mcp-server-fhf0bzdxdnced7fj.australiaeast-01.azurewebsites.net/mcp/sse"
        }
    }

# Only set up MCP SSE if the mcp module loaded successfully
if mcp is not None:
    # Create SSE transport
    sse_transport = SseServerTransport("/mcp/messages/")

    @app.get("/mcp/sse")
    async def handle_mcp_sse(request: Request):
        """Handle SSE connections for MCP communication"""
        try:
            async with sse_transport.connect_sse(request.scope, request.receive, request._send) as streams:
                await mcp._mcp_server.run(
                    streams[0], streams[1], mcp._mcp_server.create_initialization_options()
                )
            return Response()
        except Exception as e:
            print(f"SSE handler error: {e}")
            return Response(status_code=500)

    # Mount the message handler
    try:
        app.mount("/mcp/messages/", sse_transport.handle_post_message)
    except Exception as e:
        print(f"Failed to mount message handler: {e}")
else:
    @app.get("/mcp/sse")
    async def handle_mcp_sse_fallback():
        return {"error": "MCP module not available"}

# For Azure App Service deployment
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")