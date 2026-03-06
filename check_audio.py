"""Quick diagnostic to check available audio devices for the stream listener."""
import pyaudio

p = pyaudio.PyAudio()

print(f"Found {p.get_device_count()} audio devices:\n")
print(f"{'ID':>3}  {'Inputs':>6}  {'Outputs':>7}  Name")
print("-" * 70)

for i in range(p.get_device_count()):
    dev = p.get_device_info_by_index(i)
    name = dev["name"]
    inputs = dev["maxInputChannels"]
    outputs = dev["maxOutputChannels"]
    rate = int(dev["defaultSampleRate"])
    marker = ""
    name_lower = name.lower()
    if inputs > 0 and ("loopback" in name_lower or "stereo mix" in name_lower
                        or "what u hear" in name_lower or "wave out" in name_lower):
        marker = "  <-- LOOPBACK"
    print(f"{i:>3}  {inputs:>6}  {outputs:>7}  {name} ({rate}Hz){marker}")

print()
try:
    default_in = p.get_default_input_device_info()
    print(f"Default input device: [{default_in['index']}] {default_in['name']}")
except Exception as e:
    print(f"No default input device: {e}")

try:
    default_out = p.get_default_output_device_info()
    print(f"Default output device: [{default_out['index']}] {default_out['name']}")
except Exception as e:
    print(f"No default output device: {e}")

p.terminate()
