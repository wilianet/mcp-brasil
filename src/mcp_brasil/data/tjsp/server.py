"""TJSP feature server — registers tools and resources.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .resources import info_tjsp
from .tools import buscar_acordaos_tjsp

mcp = FastMCP("mcp-brasil-tjsp")

mcp.tool(buscar_acordaos_tjsp, tags={"busca", "jurisprudencia", "tjsp", "acordaos"})

mcp.resource("data://tjsp/info", mime_type="application/json")(info_tjsp)
