import argparse
from pathlib import Path
import onnxruntime as ort
from onnxruntime.quantization import quantize_dynamic, QuantType

def quantize_to_int8(model_path: Path, output_path: Path) -> None:
    """Quantize FP32 ONNX model to INT8 using dynamic quantization."""
    print(f"Quantizing {model_path} to {output_path}...")
    quantize_dynamic(
        model_input=str(model_path),
        model_output=str(output_path),
        weight_type=QuantType.QInt8,
    )
    print("Quantization complete!")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--onnx-path", default="gesture_controller/data/hand_landmark.onnx")
    parser.add_argument("--output-path", default="gesture_controller/data/hand_landmark_int8.onnx")
    args = parser.parse_args()

    model_path = Path(args.onnx_path)
    output_path = Path(args.output_path)

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    quantize_to_int8(model_path, output_path)

if __name__ == "__main__":
    main()
