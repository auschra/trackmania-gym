import socket
import struct
import time
from threading import Lock, Thread, Event
import select
import errno  # Import errno for socket error codes

class TMClient:
    def __init__(self, host='localhost', port=9000, max_reconnect_attempts=-1, reconnect_delay=1): # -1 for infinite retries
        self._struct_str = '<' + 'f' * 19
        self._nb_bytes = struct.calcsize(self._struct_str)
        self._host = host
        self._port = port
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay # Delay between reconnection attempts

        self.__lock = Lock()
        self.__data = None
        self.__running = True
        self.__connected = Event()
        self.__socket = None  # Store the socket object
        self.__t_client = Thread(target=self.__client_thread, daemon=True)
        self.__t_client.start()

    def __connect(self): # removed sock parameter as now using self.__socket
        attempts = 0
        while self.__running and (self.max_reconnect_attempts == -1 or attempts < self.max_reconnect_attempts): # added infinte retries option
            try:
                print(f"Attempting to connect to {self._host}:{self._port} (Attempt {attempts + 1})...")
                self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Create socket here
                self.__socket.connect((self._host, self._port))
                self.__socket.setblocking(0)  # Non-blocking
                print(f"Connected successfully!")
                self.__connected.set()
                return True
            except ConnectionRefusedError:
                print("Connection refused. Retrying...")
            except socket.error as e:
                print(f"Socket error while connecting: {e}")
            finally:
                attempts += 1
                if self.__running:
                    time.sleep(self.reconnect_delay) # use reconnect delay

        print("Max reconnection attempts reached (or stopped).")
        return False

    def __client_thread(self):
        while self.__running:
            if not self.__connect():
                break # if connect fails exit the thread
            
            data_raw = b''
            while self.__running:
                ready_to_read, _, _ = select.select([self.__socket], [], [], 1.0)
                if self.__socket in ready_to_read:
                    try:
                        chunk = self.__socket.recv(4096)
                        if not chunk:
                            print("Server closed connection.")
                            break  # Reconnect
                        data_raw += chunk
                        while len(data_raw) >= self._nb_bytes:
                            data_msg = data_raw[:self._nb_bytes]
                            data_raw = data_raw[self._nb_bytes:]
                            with self.__lock:
                                self.__data = data_msg
                    except socket.error as e:
                        if e.errno == errno.ECONNRESET: # Check for connection reset
                            print("Connection reset by peer.")
                            break
                        elif e.errno == errno.EPIPE: # Check for broken pipe
                            print("Broken Pipe")
                            break
                        else:
                            print(f"Socket error during recv: {e}")
                            break # Reconnect on other errors as well
                else:
                    # Timeout, check if still connected by sending a heartbeat
                    try:
                        self.__socket.send(b'') # sending empty bytes acts as a heartbeat
                    except socket.error as e:
                        if e.errno == errno.EPIPE or e.errno == errno.ECONNRESET:
                            print("Heartbeat failed, connection lost")
                            break
                        else:
                            print(f"Heartbeat error: {e}")
                            break
            self.__connected.clear()
            if self.__socket:
                self.__socket.close()
                self.__socket = None
            print("Attempting to reconnect...")
        print("Client thread finished.")

    # ... (retrieve_data, is_connected, close remain the same)

    def retrieve_data(self, sleep_if_empty=0.01, timeout=10.0):
        if not self.__connected.wait(timeout):
            raise TimeoutError("Failed to connect to the server")
            
        start_time = time.time()
        while self.__running:
            with self.__lock:
                if self.__data is not None:
                    try:
                        data = struct.unpack(self._struct_str, self.__data)
                        self.__data = None
                        
                        result = {
                            'checkpoint': int(data[0]),
                            'lap': int(data[1]),
                            'speed': data[2],
                            'position': {'x': data[3], 'y': data[4], 'z': data[5]},
                            'steer': data[6],
                            'gas': data[7],
                            'brake': bool(data[8]),
                            'finished': bool(data[9]),
                            'acceleration': data[10],
                            'jerk': data[11],
                            'aim_yaw': data[12],
                            'aim_pitch': data[13],
                            'fl_steer_angle': data[14],
                            'fr_steer_angle': data[15],
                            'fl_slip': data[16],
                            'fr_slip': data[17],
                            'gear': int(data[18])
                        }
                        
                        #print(f"\nParsed data successfully:")
                        #print(f"Speed: {result['speed']:.2f}")
                        #print(f"Position: ({result['position']['x']:.1f}, {result['position']['y']:.1f}, {result['position']['z']:.1f})")
                        #print(f"Checkpoint: {result['checkpoint']}, Lap: {result['lap']}")
                        
                        return result
                        
                    except struct.error as e:
                        print(f"Error unpacking data: {e}")
                        continue
            
            if time.time() - start_time > timeout:
                raise TimeoutError(f"No data received for {timeout} seconds")
            
            time.sleep(sleep_if_empty)

    def is_connected(self):
        return self.__connected.is_set()

    def close(self):
        self.__running = False
        self.__connected.set()
        self.__t_client.join(timeout=1.0)
