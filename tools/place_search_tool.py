import os
from utils.place_info_search import TavilyPlaceSearchTool
from typing import List
from langchain.tools import tool
from dotenv import load_dotenv


class PlaceSearchTool:
    def __init__(self):
        load_dotenv()
        self.tavily_search = TavilyPlaceSearchTool()
        self.place_search_tool_list = self._setup_tools()

    def _setup_tools(self) -> List:
        """Setup all tools for the place search tool"""

        @tool
        def search_attractions(place: str) -> str:
            """Search attractions of a place"""
            tavily_result = self.tavily_search.tavily_search_attractions(place)
            return f"Following are the attractions of {place}: {tavily_result}"

        @tool
        def search_restaurants(place: str) -> str:
            """Search restaurants of a place"""
            tavily_result = self.tavily_search.tavily_search_restaurants(place)
            return f"Following are the restaurants of {place}: {tavily_result}"

        @tool
        def search_activities(place: str) -> str:
            """Search activities of a place"""
            tavily_result = self.tavily_search.tavily_search_activity(place)
            return f"Following are the activities in and around {place}: {tavily_result}"

        @tool
        def search_transportation(place: str) -> str:
            """Search transportation of a place"""
            tavily_result = self.tavily_search.tavily_search_transportation(place)
            return f"Following are the modes of transportation available in {place}: {tavily_result}"

        return [search_attractions, search_restaurants, search_activities, search_transportation]
