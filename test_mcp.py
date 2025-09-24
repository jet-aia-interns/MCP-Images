#!/usr/bin/env python3
"""
Test script for the Image MCP Server
"""
import asyncio
import json
from mcp_image import mcp

async def test_image_search():
    """Test the image search functionality"""
    print("Testing search_google_images...")
    
    try:
        # Test the search functionality directly by calling the function from mcp_image
        from mcp_image import search_google_images
        result = await search_google_images(search_query="sunset", max_results=3)
        print(f"Search result: {json.dumps(result, indent=2)}")
        return True
    except Exception as e:
        print(f"Error during search: {e}")
        return False

async def test_all_tools():
    """Test that all tools are available"""
    print("Available MCP tools:")
    tools = list(mcp._tool_manager._tools.keys())
    for i, tool in enumerate(tools, 1):
        print(f"{i}. {tool}")
    
    print(f"\nTotal tools available: {len(tools)}")
    return len(tools) > 0

async def main():
    """Main test function"""
    print("=" * 50)
    print("Image MCP Server Local Test")
    print("=" * 50)
    
    # Test 1: Check available tools
    print("\n1. Testing tool availability...")
    tools_available = await test_all_tools()
    
    if not tools_available:
        print("❌ No tools available!")
        return
    
    print("✅ Tools are available!")
    
    # Test 2: Test image search
    print("\n2. Testing image search...")
    search_success = await test_image_search()
    
    if search_success:
        print("✅ Image search test completed!")
    else:
        print("❌ Image search test failed!")
    
    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(main())