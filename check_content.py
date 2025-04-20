import io
import os

from google.cloud import vision_v1

from os import listdir
import proto
#from google.cloud import storage
#os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"/Users/example/Documents/Project/ServiceAccountTolken.json"

def loadImages(path):
    # return array of bytes

    loadedImages = []

    with io.open(path, 'rb') as image:
        content = image.read()
    loadedImages.append(content)

    return content


def batch_annotate(contents):
    """Perform async batch image annotation."""
    client = vision_v1.ImageAnnotatorClient()

    requests = []

    image = {"content": contents}
    features = [
        {"type_": vision_v1.Feature.Type.SAFE_SEARCH_DETECTION},
    ]
    requests = [{"image": image, "features": features}]

    response = client.batch_annotate_images(requests=requests,)
    to_text = proto.Message.to_dict(response) # convert object to text
    print(to_text['responses'][0]['safe_search_annotation']['adult'])

path_to_image = 'pyth-3.12-user-auth/data/images.jpeg'
batch_annotate(loadImages(path_to_image))