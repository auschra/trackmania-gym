import socket
import struct
import time
from threading import Lock, Thread, Event

class TMClient:
    def __init__(self, host='localhost', port=9000, max_reconnect_attempts=5):
        self._struct_str = '<' + 'f' * 19
        self._nb_bytes = struct.calcsize(self._struct_str)
        #print(f"Expecting {self._nb_bytes} bytes per message ({19} floats)")
        self._host = host
        self._port = port
        self.max_reconnect_attempts = max_reconnect_attempts
        
        self.__lock = Lock()
        self.__data = None
        self.__running = True
        self.__connected = Event()
        self.__t_client = Thread(target=self.__client_thread, daemon=True)
        self.__t_client.start()

    def __connect(self, sock):
        attempts = 0
        while self.__running and attempts < self.max_reconnect_attempts:
            try:
                print(f"Attempting to connect to {self._host}:{self._port} (Attempt {attempts + 1}/{self.max_reconnect_attempts})...")
                sock.connect((self._host, self._port))
                sock.settimeout(1.0)
                print(f"Connected successfully!")
                self.__connected.set()
                return True
            except ConnectionRefusedError:
                print("Connection refused. Retrying in 1 second...")
                time.sleep(1)
            except socket.error as e:
                print(f"Socket error while connecting: {e}")
                time.sleep(1)
            attempts += 1
        print("Max reconnection attempts reached. Stopping reconnection attempts.")
        return False

    def __client_thread(self):
        while self.__running:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    if not self.__connect(s):
                        break
                    
                    data_raw = b''
                    msg_count = 0
                    
                    while self.__running:
                        try:
                            # Try to read exact amount needed
                            bytes_needed = self._nb_bytes - len(data_raw)
                            #print(f"\nWaiting for {bytes_needed} bytes...")
                            
                            chunk = s.recv(bytes_needed)
                            chunk_size = len(chunk)
                            
                            if chunk_size == 0:
                                print("Server closed connection (received 0 bytes)")
                                break
                            
                            #print(f"Received chunk of {chunk_size} bytes")
                            data_raw += chunk
                            current_buffer = len(data_raw)
                            #print(f"Current buffer size: {current_buffer} bytes")
                            
                            # Process complete messages
                            while len(data_raw) >= self._nb_bytes:
                                msg_count += 1
                                #print(f"\nProcessing message #{msg_count}")
                                
                                # Extract one complete message
                                data_msg = data_raw[:self._nb_bytes]
                                data_raw = data_raw[self._nb_bytes:]
                                
                                #print(f"Message size: {len(data_msg)} bytes")
                                #print(f"Remaining buffer: {len(data_raw)} bytes")
                                
                                # Store the latest message
                                with self.__lock:
                                    self.__data = data_msg
                            
                        except socket.timeout:
                            # This is normal - just means no new data for 1 second
                            continue
                        except ConnectionError as e:
                            print(f"Connection error: {e}")
                            break
                    
                    self.__connected.clear()
                    print("Connection lost, attempting to reconnect...")
                    
            except Exception as e:
                print(f"Error in client thread: {e}")
                time.sleep(1)

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
                        '''
                        print(f"\nParsed data successfully:")
                        print(f"Speed: {result['speed']:.2f}")
                        print(f"Position: ({result['position']['x']:.1f}, {result['position']['y']:.1f}, {result['position']['z']:.1f})")
                        print(f"Checkpoint: {result['checkpoint']}, Lap: {result['lap']}")
                        '''
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

# The main function is removed to allow importing and using the TMClient class from other scripts