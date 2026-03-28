import socket
import json
import time
import select
from typing import Dict, Any, Optional

class NetworkClient:
    """Handles communication with the game server."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.buffer = ""
        self.is_connected = False

    def connect(self) -> bool:
        """Establishes a connection to the server."""
        if self.is_connected and self.socket:
            print("Already connected.")
            return True
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0) # Timeout for connection attempt
            self.socket.connect((self.host, self.port))
            self.socket.settimeout(None) # Reset timeout for blocking reads
            self.is_connected = True
            self.buffer = "" # Clear buffer on new connection
            print(f"Successfully connected to server at {self.host}:{self.port}")
            return True
        except socket.error as e:
            print(f"Failed to connect to server: {e}")
            self.socket = None
            self.is_connected = False
            return False
        except Exception as e:
            print(f"An unexpected error occurred during connection: {e}")
            self.socket = None
            self.is_connected = False
            return False


    def disconnect(self):
        """Closes the connection to the server."""
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except socket.error as e:
                print(f"Error closing socket: {e}")
            finally:
                self.socket = None
                self.is_connected = False
                print("Disconnected from server.")
        else:
            print("Not connected.")

    def send_request(self, action: str, payload: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Sends a request to the server and waits for a response.

        Args:
            action: The command identifier (e.g., 'get_squad').
            payload: Optional dictionary containing data for the action.

        Returns:
            A dictionary representing the server's JSON response, or None on error/disconnect.
        """
        if not self.is_connected or not self.socket:
            print("Error: Not connected to server.")
            return None

        try:
            request_data = {"action": action, "payload": payload or {}}
            message = json.dumps(request_data) + '\n'
            self.socket.sendall(message.encode('utf-8'))
            # print(f"Sent: {message.strip()}") # Debug

            # --- Receive Response ---
            start_time = time.time()
            timeout = 10.0 # 10 second timeout for response

            while '\n' not in self.buffer:
                 # Check for timeout
                 if time.time() - start_time > timeout:
                     print("Error: Timeout waiting for server response.")
                     self.disconnect() # Assume connection issue
                     return None

                 ready_to_read, _, _ = select.select([self.socket], [], [], 0.1) # Non-blocking check
                 if ready_to_read:
                     chunk = self.socket.recv(1024)
                     if not chunk:
                         print("Error: Server disconnected while waiting for response.")
                         self.disconnect()
                         return None
                     self.buffer += chunk.decode('utf-8')


            # Process the complete message
            response_str, self.buffer = self.buffer.split('\n', 1)
            # print(f"Received: {response_str}") # Debug
            response = json.loads(response_str)
            return response

        except (socket.error, BrokenPipeError, ConnectionResetError) as e:
            print(f"Network Error: {e}. Disconnecting.")
            self.disconnect()
            return None
        except json.JSONDecodeError as e:
             print(f"Error decoding server response: {e}. Response: '{response_str}'")
             # Don't necessarily disconnect here, could be a bad message
             return {"status": "error", "data": None, "message": "Invalid JSON from server"}
        except Exception as e:
            print(f"An unexpected error occurred during send/receive: {e}")
            self.disconnect() # Disconnect on unknown errors
            return None

