
### print banner

# MCP Server version - updated automatically during build
# DO NOT CHANGE THIS LINE FORMAT - it is replaced by CI/CD pipeline
SERVER_VERSION = "dev"  # Replaced by CI

def jadx_mcp_server_banner() -> str:
    """
    Generate ASCII art banner for server startup.

    Returns:
        str: Multi-line ASCII art banner with project information

    Note:
        Displayed on server startup if terminal supports Unicode characters
    """
    return f"""
                ░█████    ░███    ░███████   ░██    ░██       ░███    ░██████   ░███     ░███   ░██████  ░█████████  
                  ░██    ░██░██   ░██   ░██   ░██  ░██       ░██░██     ░██     ░████   ░████  ░██   ░██ ░██     ░██ 
                  ░██   ░██  ░██  ░██    ░██   ░██░██       ░██  ░██    ░██     ░██░██ ░██░██ ░██        ░██     ░██ 
                  ░██  ░█████████ ░██    ░██    ░███       ░█████████   ░██     ░██ ░████ ░██ ░██        ░█████████  
            ░██   ░██  ░██    ░██ ░██    ░██   ░██░██      ░██    ░██   ░██     ░██  ░██  ░██ ░██        ░██         
            ░██   ░██  ░██    ░██ ░██   ░██   ░██  ░██     ░██    ░██   ░██     ░██       ░██  ░██   ░██ ░██         
             ░██████   ░██    ░██ ░███████   ░██    ░██    ░██    ░██ ░██████   ░██       ░██   ░██████  ░██         
            
            
            
            Original Author -\u003e Jafar Pathan (zinja-coder@github)
            Fork Maintainer -\u003e xjoker (https://github.com/xjoker)
            Project URL     -\u003e https://github.com/xjoker/jadx-ai-mcp
            Server Version  -\u003e v{SERVER_VERSION}
            
          """

