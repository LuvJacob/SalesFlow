"""SalesFlow MCP server (scaffold).

Lane B owns this file. Only a `ping` health-check tool exists so the Bob-to-MCP
connection can be verified. The four production tools defined in
docs/contracts/mcp-tools.md are NOT implemented yet:
  get_account_profile, get_opportunity_context,
  search_product_knowledge, get_sales_playbook

Transport is stdio. Never print to stdout: it carries the MCP protocol stream.
Log to stderr only.
"""

from fastmcp import FastMCP

mcp = FastMCP("salesflow")


@mcp.tool
def ping() -> dict:
    """Health check. Confirms the SalesFlow MCP server is running. Reads no data."""
    return {"status": "ok", "data": {"server": "salesflow", "version": "0.1.0"}}


def main() -> None:
    mcp.run()  # stdio transport by default


if __name__ == "__main__":
    main()
