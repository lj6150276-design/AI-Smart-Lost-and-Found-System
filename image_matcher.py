import torch
from torchvision import models, transforms
from PIL import Image
import torch.nn.functional as F


# Pre-trained ResNet model
model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)

# Last classification layer remove
model = torch.nn.Sequential(*list(model.children())[:-1])

model.eval()


transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])


def get_image_embedding(image_path):

    try:
        image = Image.open(image_path).convert("RGB")

        image = transform(image)
        image = image.unsqueeze(0)

        with torch.no_grad():
            features = model(image)

        features = features.view(features.size(0), -1)

        return features

    except Exception as error:
        print("Image processing error:", error)
        return None


def compare_images(image1_path, image2_path):

    embedding1 = get_image_embedding(image1_path)
    embedding2 = get_image_embedding(image2_path)

    if embedding1 is None or embedding2 is None:
        return 0

    similarity = F.cosine_similarity(
        embedding1,
        embedding2
    ).item()

    # Convert -1 to 1 range into percentage
    score = ((similarity + 1) / 2) * 100

    return round(score, 2)