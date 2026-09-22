import os, hashlib, math
from PIL import Image, ImageStat, ImageFilter

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
MODEL_PATH=os.path.join(BASE_DIR,'models','crop_grade.pt')
GENERIC_MODEL_PATH=os.path.join(BASE_DIR,'yolo11n-cls.pt')
_MODEL=None
_MODEL_KIND=None

def calculate_image_hash(path):
    sha=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(65536),b''): sha.update(b)
    return sha.hexdigest()

def normalize_grade(name):
    v=str(name).upper().strip().replace('GRADE_','').replace('GRADE ','').replace('-','')
    if v in {'A','CLASSA'}:return 'A'
    if v in {'B','CLASSB'}:return 'B'
    if v in {'C','CLASSC'}:return 'C'
    raise ValueError(f'Unknown YOLO grading class: {name}. Expected Grade_A, Grade_B or Grade_C.')

def load_quality_model():
    global _MODEL,_MODEL_KIND
    if _MODEL is not None:return _MODEL,_MODEL_KIND
    try: from ultralytics import YOLO
    except ImportError as e: raise RuntimeError('Ultralytics is not installed. Run python -m pip install -r requirements.txt') from e
    if os.path.exists(MODEL_PATH):
        _MODEL=YOLO(MODEL_PATH);_MODEL_KIND='TRAINED_CROP_GRADE';return _MODEL,_MODEL_KIND
    if os.path.exists(GENERIC_MODEL_PATH):
        _MODEL=YOLO(GENERIC_MODEL_PATH);_MODEL_KIND='DEMO_YOLO_VALIDATION';return _MODEL,_MODEL_KIND
    raise FileNotFoundError('No YOLO model found. Train models/crop_grade.pt with train_yolo.py or keep yolo11n-cls.pt for demo image validation.')

def _demo_image_grade(path,yolo_conf):
    # Prototype-only fallback when crop Grade_A/B/C weights have not yet been trained.
    # It never claims validated agricultural grading. YOLO is still used to validate live image inference.
    im=Image.open(path).convert('RGB').resize((256,256))
    stat=ImageStat.Stat(im); brightness=sum(stat.mean)/3/255
    gray=im.convert('L'); edges=gray.filter(ImageFilter.FIND_EDGES); sharp=ImageStat.Stat(edges).mean[0]/255
    score=max(0,min(1,0.50*yolo_conf+0.25*(1-abs(brightness-.55))+0.25*min(1,sharp*4)))
    grade='A' if score>=.66 else ('B' if score>=.48 else 'C')
    return grade,round(max(.45,min(.88,score)),4)

def analyze_produce_image(image_path,crop=''):
    model,kind=load_quality_model()
    results=model.predict(source=image_path,verbose=False)
    if not results:raise RuntimeError('YOLO produced no prediction')
    r=results[0]
    if r.probs is None:raise RuntimeError('The installed YOLO model is not a classification model.')
    idx=int(r.probs.top1); conf=float(r.probs.top1conf); cls=r.names[idx]
    if kind=='TRAINED_CROP_GRADE':
        grade=normalize_grade(cls);final_conf=conf;validated=True;model_label=os.path.basename(MODEL_PATH)
    else:
        grade,final_conf=_demo_image_grade(image_path,conf);validated=False;model_label='YOLO demo validator + image-quality heuristic (NOT trained crop-grade weights)'
    return {'crop':crop,'grade':grade,'confidence':round(final_conf,4),'confidence_percent':round(final_conf*100,2),'class_name':cls,'model':model_label,'validated_crop_model':validated,'image_sha256':calculate_image_hash(image_path)}
