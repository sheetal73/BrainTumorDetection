# -*- coding: utf-8 -*-
"""Brain-Tumor-Detection.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1jK57LdBZ5PWgudbjK0UY2B5S1cnPrzZS
"""

# First off we'll be cloning the mask R-CNN code implementation from given link.
!git clone https://github.com/matterport/Mask_RCNN.git
# Then well also clone the datasets and annotations provided in kaggle that has brain scans with tumor 
!git clone https://github.com/ruslan-kl/brain-tumor.git 
!pip install pycocotools

!rm -rf brain-tumor/.git/
!rm -rf Mask_RCNN/.git/


clear_output()

import os 
import sys
from tqdm import tqdm
import cv2
import numpy as np
import json
import skimage.draw
import matplotlib
import matplotlib.pyplot as plt
import random

ROOT_DIR = os.path.abspath('Mask_RCNN/') #setting root directory of the project

#we're importing mask rcnn
sys.path.append(ROOT_DIR) #finding local version of the library
from mrcnn.config import Config
from mrcnn import utils
from mrcnn.model import log
import mrcnn.model as modellib
from mrcnn import visualize


# Import COCO config
sys.path.append(os.path.join(ROOT_DIR, 'samples/coco/'))
import coco

COCO_WEIGHTS_PATH = os.path.join(ROOT_DIR, "mask_rcnn_coco.h5")#paths to trained weights
if not os.path.exists(COCO_WEIGHTS_PATH):
    utils.download_trained_weights(COCO_WEIGHTS_PATH)


 # directory to save logs and model checkpoints for trained model
MODEL_DIR = os.path.join(ROOT_DIR, 'logs')

DATASET_DIR = 'brain-tumor/data_cleaned/' # directory with image data from the cloned datasets
DEFAULT_LOGS_DIR = 'logs' 


plt.rcParams['figure.facecolor'] = 'white'

def get_ax(rows=1, cols=1, size=7):
   
    _, ax = plt.subplots(rows, cols, figsize=(size*cols, size*rows))
    return ax

MODEL_DIR = os.path.join(ROOT_DIR, 'logs') # directory to save logs and trained model
DATASET_DIR = 'brain-tumor/data_cleaned/' # directory with image data
DEFAULT_LOGS_DIR = 'logs' 

# Local path to trained weights file
COCO_MODEL_PATH = os.path.join(ROOT_DIR, "mask_rcnn_coco.h5")
if not os.path.exists(COCO_MODEL_PATH):
    utils.download_trained_weights(COCO_MODEL_PATH)

#configuring our model with the below configurations like name sa TUMOR_SHERLOCK and learning rate 0.001 which is default etc.
class TumorConfig(Config):
    NAME = 'TUMOR_SHERLOCK'
    LEARNING_RATE = 0.001
    NUM_CLASSES = 1 + 1 
    DETECTION_MIN_CONFIDENCE = 0.85    
    GPU_COUNT = 1
    IMAGES_PER_GPU = 1
    STEPS_PER_EPOCH = 50
   
config = TumorConfig()
config.display() #displaying the configurations set

class BrainScanDataset(utils.Dataset):

    def load_brain_scan(self, dataset_dir, subset):
        
        self.add_class("tumor", 1, "tumor") #adding the classes
        assert subset in ["train", "val", 'test']
        dataset_dir = os.path.join(dataset_dir, subset)

        annotations = json.load(open(os.path.join(DATASET_DIR, subset, 'annotations_'+subset+'.json')))
        annotations = list(annotations.values()) 

        
        annotations = [a for a in annotations if a['regions']]
        #addning images and the x and y coordinates of the images
        #converting polygons to mask
        for a in annotations:
           
            if type(a['regions']) is dict:
                polygons = [r['shape_attributes'] for r in a['regions'].values()]
            else:
                polygons = [r['shape_attributes'] for r in a['regions']]
            image_path = os.path.join(dataset_dir, a['filename'])
            image = skimage.io.imread(image_path)
            height, width = image.shape[:2]

            #using idforimage as unique image id
            self.add_image(
                "tumor",
                image_id=a['idforimage'], 
                path=image_path,
                width=width,
                height=height,
                polygons=polygons
            )


    #Generating instance masks for an image which returns a mask
    def load_mask(self, image_id):

        image_info = self.image_info[image_id]
        if image_info["source"] != "tumor":
            return super(self.__class__, self).load_mask(image_id)

        # Converting polygons to a bitmap mask of shape
        info = self.image_info[image_id]
        mask = np.zeros([info["height"], info["width"], len(info["polygons"])],
                        dtype=np.uint8)
        for i, p in enumerate(info["polygons"]):
            rr, cc = skimage.draw.polygon(p['all_points_y'], p['all_points_x'])
            mask[rr, cc, i] = 1

        return mask.astype(np.bool), np.ones([mask.shape[-1]], dtype=np.int32)  # returning mask, array of class IDs

    def image_reference(self, image_id):
        info = self.image_info[image_id]
        if info["source"] == "tumor":
            return info["path"]
        else:
            super(self.__class__, self).image_reference(image_id)

            #returning path of the image.

#in here we're initializing the model for traning using the config instance that we had created
#loading the pre-trained weights
model = modellib.MaskRCNN(
    mode='training', 
    config=config, 
    model_dir=DEFAULT_LOGS_DIR
)
#loading and also executing the last few layers, reason being our data set is very small,so just the heads should do.
model.load_weights(
    COCO_MODEL_PATH, 
    by_name=True, 
    exclude=["mrcnn_class_logits", "mrcnn_bbox_fc", "mrcnn_bbox", "mrcnn_mask"]
)

# now that the data sets are loaded we'll train our model for 15 epochs 
#Training dataset.
dataset_train = BrainScanDataset()
dataset_train.load_brain_scan(DATASET_DIR, 'train')
dataset_train.prepare()

# Validation dataset
dataset_val = BrainScanDataset()
dataset_val.load_brain_scan(DATASET_DIR, 'val')
dataset_val.prepare()

dataset_test = BrainScanDataset()
dataset_test.load_brain_scan(DATASET_DIR, 'test')
dataset_test.prepare()
#our learning rate is 0.001 that is also the default
#we wont be traning for very long also we have excluded few layers.
print("Training network heads")
model.train(
    dataset_train, dataset_val,
    learning_rate=config.LEARNING_RATE,
    epochs=15,
    layers='heads'
)

#here we're recreating the model in inference mode
model = modellib.MaskRCNN(
    mode="inference", 
    config=config,
    model_dir=DEFAULT_LOGS_DIR
)

#by inference we mean process of taking a model thats already been trained.
#like our model above which is already trained
#we'll use this model to make predictions
model_path = model.find_last()

# Load ing trained weights
print("Loading weights from ", model_path)
model.load_weights(model_path, by_name=True)

#here we'll build a function to display results
def predict_and_plot_differences(dataset, img_id):
    original_image, image_meta, gt_class_id, gt_box, gt_mask =\
        modellib.load_image_gt(dataset, config, 
                               img_id, use_mini_mask=False)

    results = model.detect([original_image], verbose=0)
    r = results[0]

    visualize.display_differences(
        original_image,
        gt_box, gt_class_id, gt_mask,
        r['rois'], r['class_ids'], r['scores'], r['masks'],
        class_names = ['tumor'], title="", ax=get_ax(),
        show_mask=True, show_box=True)
    
#creating a function that will display the images/ results in given or set attirbutes
def display_image(dataset, ind):
    plt.figure(figsize=(5,5))
    plt.imshow(dataset.load_image(ind))
    plt.xticks([])
    plt.yticks([])
    plt.title('Original Image')
    plt.show()

#testing model for validaton set
ind = 9 
display_image(dataset_val, ind)
predict_and_plot_differences(dataset_val, ind)

#taking another images (random) with index 6
ind = 6 
display_image(dataset_val, ind)
predict_and_plot_differences(dataset_val, ind)

#Test Set
#also tetsing the model for test set
ind = 1
display_image(dataset_test, ind)
predict_and_plot_differences(dataset_test, ind)
ind = 0 #taking another images (random) with index 0
display_image(dataset_test, ind)
predict_and_plot_differences(dataset_test, ind)



model_path = os.path.join(MODEL_DIR, 'mask_rcnn_coco.h5')
model.keras_model.save_weights(model_path)