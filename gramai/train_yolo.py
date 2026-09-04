import os
import shutil
from ultralytics import YOLO


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATASET_PATH = os.path.join(
    BASE_DIR,
    "crop_grade_dataset"
)

TRAINING_OUTPUT = os.path.join(
    BASE_DIR,
    "yolo_training"
)

FINAL_MODEL = os.path.join(
    BASE_DIR,
    "models",
    "crop_grade.pt"
)


def count_images(folder):
    extensions = (".jpg", ".jpeg", ".png", ".webp")

    return len([
        f for f in os.listdir(folder)
        if f.lower().endswith(extensions)
    ])


def train():

    print()
    print("==============================================")
    print("GRAM AI - YOLO PRODUCE QUALITY TRAINING")
    print("==============================================")
    print()

    print("Dataset path:")
    print(DATASET_PATH)
    print()

    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(
            f"Dataset folder not found: {DATASET_PATH}"
        )

    required = [
        "train/Grade_A",
        "train/Grade_B",
        "train/Grade_C",
        "val/Grade_A",
        "val/Grade_B",
        "val/Grade_C",
    ]

    print("Checking dataset...")
    print()

    for relative in required:

        folder = os.path.join(
            DATASET_PATH,
            *relative.split("/")
        )

        if not os.path.isdir(folder):
            raise FileNotFoundError(
                f"Missing folder: {folder}"
            )

        total = count_images(folder)

        print(
            f"{relative}: {total} images"
        )

        if total == 0:
            raise RuntimeError(
                f"No images found inside {relative}"
            )

    print()
    print("Dataset check passed.")
    print()

    print("Loading YOLO11 classification model...")

    model = YOLO(
        "yolo11n-cls.pt"
    )

    print()
    print("Starting model training...")
    print()

    results = model.train(
        data=DATASET_PATH,
        epochs=20,
        imgsz=224,
        batch=8,
        patience=5,
        project=TRAINING_OUTPUT,
        name="gram_ai_crop_quality",
        exist_ok=True
    )

    print()
    print("YOLO training finished.")
    print()

    best_model = os.path.join(
        TRAINING_OUTPUT,
        "gram_ai_crop_quality",
        "weights",
        "best.pt"
    )

    print("Looking for trained model:")
    print(best_model)

    if not os.path.exists(best_model):
        raise FileNotFoundError(
            "Training completed but best.pt was not found."
        )

    os.makedirs(
        os.path.dirname(FINAL_MODEL),
        exist_ok=True
    )

    shutil.copy2(
        best_model,
        FINAL_MODEL
    )

    print()
    print("==============================================")
    print("GRAM AI MODEL CREATED SUCCESSFULLY")
    print("==============================================")
    print()

    print("Model saved to:")
    print(FINAL_MODEL)


if __name__ == "__main__":
    train()