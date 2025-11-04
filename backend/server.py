import os
import json
import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import ContractLogicError
from web3.contract import Contract # Import Contract type hint
from typing import Set

# Import FastMCP components
from mcp.server.fastmcp import FastMCP, Context
#from fastmcp import FastMCP, Context

# Load environment variables from .env file
load_dotenv()

# --- Helper function ---
def parse_address_list(env_value: str | None) -> Set[str]:
    if not env_value:
        return set()
    return {Web3.to_checksum_address(addr.strip()) for addr in env_value.split(",") if Web3.is_address(addr.strip())}

# --- Configuration ---
NETWORK_RPC_URL = os.getenv("NETWORK_RPC_URL")
NETWORK_ID = os.getenv("NETWORK_ID")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
# Ensure the private key does not have the '0x' prefix for web3.py account loading
if PRIVATE_KEY and PRIVATE_KEY.startswith('0x'):
    PRIVATE_KEY = PRIVATE_KEY[2:]

TOKEN_CONTRACT_ADDRESS = os.getenv("ERC20_TOKEN_ADDRESS")
#TOKEN_DECIMALS = int(os.getenv("ERC20_TOKEN_DECIMALS", 18)) # Default to 18 if not set

ETH_WHITELIST = parse_address_list(os.getenv("ETH_WHITELIST"))
ERC20_WHITELIST = parse_address_list(os.getenv("ERC20_WHITELIST"))

# Standard ERC20 ABI (only the functions we need: 'balanceOf' and 'transfer')
ERC20_ABI = json.loads("""
[
    {
        "constant": true,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": false,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "success", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": true,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]
""")



# --- Web3 Context ---
@dataclass
class Web3Context:
    """Context holding the Web3 connection and related objects."""
    w3: Web3 | None = None
    sender_address: str | None = None
    token_contract: Contract | None = None # Use Contract type hint
    token_decimals: int | None = None

# --- Lifespan Management ---
@asynccontextmanager
async def web3_lifespan(server: FastMCP) -> AsyncIterator[Web3Context]:
    """
    Manages the Web3 connection lifecycle for the MCP server.

    Initializes the Web3 connection, derives the sender address,
    and loads the token contract based on environment variables.
    """
    print("--- Initializing Web3 Connection (Lifespan Start) ---")
    if not NETWORK_RPC_URL:
        print("ERROR: NEWTORK_RPC_URL not found in environment variables.")
        raise ValueError("NEWTORK_RPC_URL not found in environment variables.")
    if not NETWORK_ID:
        print("ERROR: NETWORK_ID not found in environment variables.")
        raise ValueError("NETWORK_ID not found in environment variables.")
    if not PRIVATE_KEY:
        print("ERROR: PRIVATE_KEY not found in environment variables.")
        raise ValueError("PRIVATE_KEY not found in environment variables.")

    w3_instance = None
    sender_addr = None
    token_contract_instance = None

    try:
        print(f"Connecting to Network via: {NETWORK_RPC_URL}")
        w3_instance = Web3(Web3.HTTPProvider(NETWORK_RPC_URL))

        if not w3_instance.is_connected():
            raise ConnectionError(f"Failed to connect to Web3 provider at {NETWORK_RPC_URL}")

        print(f"Successfully connected to Network. Chain ID: {w3_instance.eth.chain_id}")
        if w3_instance.eth.chain_id != NETWORK_ID:
            print(f"Warning: Connected chain ID ({w3_instance.eth.chain_id}) does not match expected Network ID ({NETWORK_ID})")

        # Load account from private key
        account = w3_instance.eth.account.from_key(PRIVATE_KEY)
        sender_addr = account.address
        print(f"Using sender address: {sender_addr}")

        token_decimals = None

        # Load token contract if address is provided
        if TOKEN_CONTRACT_ADDRESS:
            if not Web3.is_address(TOKEN_CONTRACT_ADDRESS):
                raise ValueError(f"Invalid ERC20_TOKEN_ADDRESS: {TOKEN_CONTRACT_ADDRESS}")
            print(f"Loading ERC20 token contract at: {TOKEN_CONTRACT_ADDRESS}")
            token_contract_instance = w3_instance.eth.contract(
                address=Web3.to_checksum_address(TOKEN_CONTRACT_ADDRESS),
                abi=ERC20_ABI
            )
            # Call decimals function safely
            try:
                token_decimals = token_contract_instance.functions.decimals().call()
                print(f"Token has {token_decimals} decimals")
            except Exception as e:
                print(f"Warning: Could not fetch token decimals: {e}")
        else:
            print("Warning: ERC20_TOKEN_ADDRESS not set. Token functions may fail.")

        # Create and yield the context object
        context = Web3Context(
            w3=w3_instance,
            sender_address=sender_addr,
            token_contract=token_contract_instance,
            token_decimals=token_decimals
        )
        yield context

    except Exception as e:
        print(f"FATAL ERROR during Web3 initialization: {e}")
        # Ensure context resources are None if setup failed before yield
        context = Web3Context() # Yield an empty context or re-raise
        raise # Re-raise the exception to prevent server startup if critical
    finally:
        # Cleanup logic if needed (though usually not required for Web3 HTTPProvider)
        print("--- Web3 Lifespan End ---")


# --- Initialize FastMCP Server ---
mcp = FastMCP(
    tool_id="mcp_evm",
    description="MCP server for interacting with the a local Ethereum Blockchain",
    lifespan=web3_lifespan,
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "8090")) # Ensure port is int
)

# --- MCP Tools ---

@mcp.tool()
async def get_eth_balance(ctx: Context, address: str) -> str:
    """
    Gets the native ETH balance of a given Ethereum address on the local blockchain.

    Args:
        ctx: The MCP server context.
        address: The Ethereum address to check the balance of.

    Returns:
        A string indicating the ETH balance or an error message.
    """
    web3_ctx = ctx.request_context.lifespan_context
    w3 = web3_ctx.w3
    if not w3 or not w3.is_connected():
        return "Error: Web3 is not connected."
    if not Web3.is_address(address):
        return f"Error: Invalid Ethereum address provided: {address}"

    try:
        checksum_address = Web3.to_checksum_address(address)
        balance_wei = w3.eth.get_balance(checksum_address)
        balance_eth = w3.from_wei(balance_wei, 'ether')
        result = f"Balance of {checksum_address}: {balance_eth} ETH"
        print(result)
        return result
    except Exception as e:
        error_msg = f"Error getting ETH balance for {address}: {e}"
        print(error_msg)
        return error_msg

# --- Send ETH Tool ---
@mcp.tool()
async def send_eth(ctx: Context, to_address: str, amount_eth: float) -> str:
    """
    Sends ETH from the server's wallet to a specified address.

    Args:
        ctx: The MCP server context.
        to_address: The recipient Ethereum address.
        amount_eth: The amount of ETH to send.

    Returns:
        A string with the transaction hash or an error message.
    """
    web3_ctx = ctx.request_context.lifespan_context
    w3 = web3_ctx.w3
    sender_address = web3_ctx.sender_address

    if not w3 or not w3.is_connected():
        return "Error: Web3 is not connected."
    if not sender_address:
        return "Error: Sender address not configured."
    if not Web3.is_address(to_address):
        return f"Error: Invalid recipient address: {to_address}"
    if amount_eth <= 0:
        return "Error: Amount must be greater than 0."
    if not PRIVATE_KEY:
        return "Error: Private key not configured."

    checksum_to_address = Web3.to_checksum_address(to_address)
    # Check against ETH whitelist
    if checksum_to_address not in ETH_WHITELIST:
        return f"Error: Recipient address {to_address} is not whitelisted for ETH transfers."

    sender_account = w3.eth.account.from_key(PRIVATE_KEY)

    try:
        nonce = w3.eth.get_transaction_count(sender_address)
        gas_price = w3.eth.gas_price
        value_wei = w3.to_wei(amount_eth, 'ether')

        tx = {
            'chainId': int(NETWORK_ID),
            'nonce': nonce,
            'to': checksum_to_address,
            'value': value_wei,
            'gas': 21000,
            'gasPrice': gas_price
        }

        signed_tx = sender_account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = tx_hash.hex()

        print(f"ETH sent! Transaction hash: {tx_hash_hex}")
        return f"Transaction submitted. Hash: {tx_hash_hex}"

    except Exception as e:
        error_msg = f"Error sending ETH: {e}"
        print(error_msg)
        return f"Error: {error_msg}"


@mcp.tool()
async def get_erc20_token_balance(ctx: Context, wallet_address: str) -> str:
    """
    Gets the balance of the configured ERC20 token for a given wallet address.

    Uses the ERC20_TOKEN_ADDRESS defined in the .env file.

    Args:
        ctx: The MCP server context.
        wallet_address: The Ethereum address to check the token balance of.

    Returns:
        A string indicating the token balance or an error message.
    """
    web3_ctx = ctx.request_context.lifespan_context
    w3 = web3_ctx.w3
    token_contract = web3_ctx.token_contract
    sender_address = web3_ctx.sender_address # Get sender address for context

    if not w3 or not w3.is_connected():
        return "Error: Web3 is not connected."
    if not token_contract:
        return "Error: ERC20 Token contract not configured or loaded."
    if not Web3.is_address(wallet_address):
        return f"Error: Invalid wallet address provided: {wallet_address}"

    try:
        checksum_wallet_address = Web3.to_checksum_address(wallet_address)
        balance_smallest_unit = token_contract.functions.balanceOf(checksum_wallet_address).call()
        token_decimals = web3_ctx.token_decimals or 18  # fallback
        balance_normal = balance_smallest_unit / (10**token_decimals)

        result = f"Token balance of {checksum_wallet_address} ({token_contract.address}): {balance_normal}"
        print(result)

        # Add sender balance info for convenience
        if sender_address and checksum_wallet_address == Web3.to_checksum_address(sender_address):
             result += f" (This is the server's configured address)"
        elif sender_address:
             sender_checksum = Web3.to_checksum_address(sender_address)
             sender_balance_smallest = token_contract.functions.balanceOf(sender_checksum).call()
             sender_balance_normal = sender_balance_smallest / (10**token_decimals)
             print(f"Server's ({sender_address}) token balance: {sender_balance_normal}")
        return result
    except Exception as e:
        error_msg = f"Error getting token balance for {wallet_address}: {e}"
        print(error_msg)
        return error_msg


@mcp.tool()
async def get_network_gas_price(ctx: Context) -> str:
    """
    Gets the current gas price from the network.

    Args:
        ctx: The MCP server context.

    Returns:
        A string indicating the current gas price in Gwei or an error message.
    """
    web3_ctx = ctx.request_context.lifespan_context
    w3 = web3_ctx.w3
    if not w3 or not w3.is_connected():
        return "Error: Web3 is not connected."

    try:
        gas_price_wei = w3.eth.gas_price
        gas_price_gwei = w3.from_wei(gas_price_wei, 'gwei')
        result = f"Current gas price: {gas_price_gwei} Gwei"
        print(result)
        return result
    except Exception as e:
        error_msg = f"Error getting gas price: {e}"
        print(error_msg)
        return error_msg

@mcp.tool()
async def send_erc20_token(ctx: Context, to_address: str, amount: float) -> str:
    """
    Sends a specified amount of the configured ERC20 token from the server's wallet.

    Uses the PRIVATE_KEY and ERC20_TOKEN_ADDRESS defined in the .env file.
    Requires the server's wallet to have sufficient ETH for gas and sufficient tokens.

    Args:
        ctx: The MCP server context.
        to_address: The recipient Ethereum address.
        amount: The amount of tokens to send (e.g., 0.5).

    Returns:
        A string indicating the transaction hash on success, or an error message.
    """
    web3_ctx = ctx.request_context.lifespan_context
    w3 = web3_ctx.w3
    sender_address = web3_ctx.sender_address
    token_contract = web3_ctx.token_contract
    token_decimals = web3_ctx.token_decimals or 18  # fallback

    # --- Input and Context Validation ---
    if not w3 or not w3.is_connected():
        return "Error: Web3 is not connected."
    if not sender_address:
         return "Error: Sender address not configured or loaded."
    if not token_contract:
        return "Error: Token contract not configured or loaded."
    if not Web3.is_address(to_address):
        return f"Error: Invalid recipient address: {to_address}"
    if amount <= 0:
        return "Error: Amount must be positive."
    if not PRIVATE_KEY: # Check again ensure private key loaded
        return "Error: Server private key not available."

    checksum_to_address = Web3.to_checksum_address(to_address)
    # Check against ERC20 whitelist
    if checksum_to_address not in ERC20_WHITELIST:
        return f"Error: Recipient address {to_address} is not whitelisted for ERC20 transfers."

    sender_account = w3.eth.account.from_key(PRIVATE_KEY) # Need account object to sign

    # Convert amount to the token's smallest unit
    amount_in_smallest_unit = int(amount * (10**token_decimals))

    print(f"Attempting to send {amount} tokens ({amount_in_smallest_unit} smallest units) "
          f"from {sender_address} to {checksum_to_address}...")

    try:
        # 1. Get nonce
        nonce = w3.eth.get_transaction_count(sender_address)
        print(f"Using nonce: {nonce}")

        # 2. Prepare the transaction
        current_gas_price = w3.eth.gas_price
        tx_data = {
            'chainId': int(NETWORK_ID),
            'from': sender_address, # Required for estimateGas
            'gasPrice': current_gas_price,
            'nonce': nonce,
             # 'gas' will be estimated
        }

        # Estimate gas
        try:
            estimated_gas = token_contract.functions.transfer(
                checksum_to_address,
                amount_in_smallest_unit
            ).estimate_gas(tx_data) # Pass tx params for accurate estimate
            tx_data['gas'] = int(estimated_gas * 1.2) # Add 20% buffer
            print(f"Estimated gas: {estimated_gas}, using limit: {tx_data['gas']}")
        except ContractLogicError as e:
             err_msg = f"Gas estimation failed: {e}. Check sender's token balance."
             print(err_msg)
             return f"Error: {err_msg}" # Return error if estimation fails
        except Exception as e:
            tx_data['gas'] = 200000 # Fallback gas limit
            print(f"Warning: Gas estimation failed ({e}), using default limit {tx_data['gas']}")

        # Remove 'from' if it was added only for estimateGas, as build_transaction adds it
        tx_data.pop('from', None)

        # Build the final transaction object for signing
        transaction = token_contract.functions.transfer(
            checksum_to_address,
            amount_in_smallest_unit
        ).build_transaction(tx_data)

        # 3. Sign the transaction
        signed_tx = sender_account.sign_transaction(transaction)
        print("Transaction signed.")

        # 4. Send the transaction
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = tx_hash.hex()
        print(f"Transaction sent! Hash: {tx_hash_hex}")
        #print(f"View on Sepolia Etherscan: https://sepolia.etherscan.io/tx/{tx_hash_hex}")

        # 5. Wait for confirmation (Optional - uncomment if needed, but makes the tool slow)
        # print(f"Waiting for transaction receipt (this may take a while)...")
        # tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        # if tx_receipt['status'] == 1:
        #     print(f"Transaction successful! Block: {tx_receipt['blockNumber']}")
        #     return f"Success! Tx Hash: {tx_hash_hex}"
        # else:
        #     print(f"Transaction failed! Receipt: {tx_receipt}")
        #     return f"Failed! Tx Hash: {tx_hash_hex}. Check block explorer."

        # Return immediately after sending
        return f"Transaction submitted. Hash: {tx_hash_hex}"

    except ValueError as ve:
         error_msg = f"Value Error during transaction: {ve}"
         print(error_msg)
         return f"Error: {error_msg}"
    except ContractLogicError as cle:
        # This often happens due to insufficient balance or other contract rules
        error_msg = f"Contract Logic Error: {cle}"
        print(error_msg)
        return f"Contract Error: {error_msg}"
    except Exception as e:
        error_msg = f"An unexpected error occurred: {e}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return f"Unexpected Error: {e}"


# --- Main Execution Logic ---
async def main():
    """Run the MCP server with the configured transport."""
    # Example: Choose transport based on environment variable
    transport = os.getenv("TRANSPORT", "stdio").lower() # Default to STDIO

    #print(f"\nStarting Sepolia MCP Server ({mcp.tool_id})...")
    #print(f"Host: {mcp.host}, Port: {mcp.port}")
    print(f"Transport: {transport}")

    if transport == 'sse':
        print("Running with SSE transport. Access tools via HTTP requests.")
        await mcp.run_sse_async()
    elif transport == 'stdio':
        print("Running with stdio transport. Interact via console.")
        await mcp.run_stdio_async()
    else:
        print(f"Error: Unknown transport '{transport}'. Use 'sse' or 'stdio'.")

if __name__ == "__main__":
    # Basic check for essential env vars before starting asyncio loop
    if not NETWORK_RPC_URL or not NETWORK_ID or not PRIVATE_KEY:
         print("ERROR: Essential environment variables (NETWORK_RPC_URL, NETWORK_ID, PRIVATE_KEY) are missing.")
         print("Please check your .env file.")
    else:
        try:
             asyncio.run(main())
        except (ValueError, ConnectionError) as e:
             # Catch errors during lifespan setup if they weren't handled internally
             print(f"\nFailed to start server due to error during initialization: {e}")
        except KeyboardInterrupt:
             print("\nServer stopped by user.")
