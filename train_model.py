from __future__ import annotations

import json
from pathlib import Path

import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.preprocessing.image import ImageDataGenerator


def build_model(num_classes: int, image_size: int = 224) -> tf.keras.Model:
    base = MobileNetV2(
        input_shape=(image_size, image_size, 3),
        include_top=False,
        weights="imagenet",
    )
    base.trainable = False

    inputs = layers.Input(shape=(image_size, image_size, 3))
    x = base(inputs, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.2)(x)
    outputs = layers.Dense(num_classes, activation="softmax")(x)
    model = models.Model(inputs, outputs)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"
    train_dir = data_dir / "train"
    test_dir = data_dir / "test"

    if not train_dir.exists():
        raise FileNotFoundError(f"Training directory not found: {train_dir}")
    if not test_dir.exists():
        raise FileNotFoundError(f"Test directory not found: {test_dir}")

    image_size = 224
    batch_size = 32
    epochs = 3

    train_gen = ImageDataGenerator(
        preprocessing_function=tf.keras.applications.mobilenet_v2.preprocess_input,
        rotation_range=10,
        width_shift_range=0.1,
        height_shift_range=0.1,
        shear_range=0.1,
        zoom_range=0.1,
        horizontal_flip=True,
    )
    test_gen = ImageDataGenerator(
        preprocessing_function=tf.keras.applications.mobilenet_v2.preprocess_input
    )

    train_it = train_gen.flow_from_directory(
        str(train_dir),
        target_size=(image_size, image_size),
        batch_size=batch_size,
        class_mode="categorical",
        shuffle=True,
    )
    test_it = test_gen.flow_from_directory(
        str(test_dir),
        target_size=(image_size, image_size),
        batch_size=batch_size,
        class_mode="categorical",
        shuffle=False,
    )

    if len(train_it.class_indices) < 2:
        raise RuntimeError(
            "Training data must contain at least 2 class folders under data/train.\n"
            "If your dataset is flat (e.g. data/train/images/*.png), run:\n"
            "  python prepare_classifier_dataset.py\n"
            "Then rerun training."
        )

    labels = [None] * len(train_it.class_indices)
    for label, idx in train_it.class_indices.items():
        labels[idx] = label

    model = build_model(num_classes=len(labels), image_size=image_size)

    ckpt_dir = base_dir / "models"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    model_path = ckpt_dir / "disaster_model.h5"
    labels_path = ckpt_dir / "disaster_labels.json"

    callbacks = [
        tf.keras.callbacks.EarlyStopping(monitor="val_accuracy", patience=3, restore_best_weights=True),
        tf.keras.callbacks.ModelCheckpoint(filepath=str(model_path), monitor="val_accuracy", save_best_only=True),
    ]

    model.fit(
        train_it,
        validation_data=test_it,
        epochs=epochs,
        callbacks=callbacks,
        verbose=2,
    )

    labels_path.write_text(json.dumps(labels, indent=2), encoding="utf-8")
    print(f"Saved model: {model_path}")
    print(f"Saved labels: {labels_path}")


if __name__ == "__main__":
    main()

