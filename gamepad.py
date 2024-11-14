import vgamepad as vg
import time
import subprocess
import os

class GamepadHandler:
    def __init__(self):
        # uinput permissions 
        if not os.access('/dev/uinput', os.W_OK):
            raise PermissionError(
                "No write access sudo chmod +0666 /dev/uinput"
            )
        
        self.gamepad = vg.VX360Gamepad()
        print("Gamepad initialized")
        
    def send_action(self, action):
        steer, throttle, brake = action
        
        #print(f"Sending action - Steer: {steer:.2f}, Throttle: {throttle:.2f}, Brake: {brake:.2f}")
        
        # x-axis (-1 to 1)
        self.gamepad.left_joystick_float(x_value_float=steer, y_value_float=0.0)
        
        # throttle (0 to 1)
        self.gamepad.right_trigger_float(value_float=throttle)
        
        # brake (0 to 1) 
        self.gamepad.left_trigger_float(value_float=brake)
        
        # gamepad state
        self.gamepad.update()

        time.sleep(0.001)

    def reset(self):
        self.gamepad.reset()
        self.gamepad.press_button(button=0x2000)  # reset press
        self.gamepad.update()
        time.sleep(0.05)
        self.gamepad.release_button(button=0x2000) # reset release
        self.gamepad.reset() 
        self.gamepad.update()
