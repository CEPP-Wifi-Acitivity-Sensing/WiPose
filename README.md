#WiPose

Download dataset:
<https://github.com/NjtechCVLab/Wi-PoseDataset>

Install dependencies:
```bash
pip install -r requirements.txt
```

Train and export:
```bash
python train.py --train-dir Wi-Pose\Train --output-dir artifacts\wi-pose --epochs 30 --batch-size 256 --workers 0
```

Use the exported model:
```bash
python train.py --predict Wi-Pose\Test\bend_009-frame001.mat --model-dir artifacts\wi-pose
```

The exported files are:
```
artifacts\wi-pose\wi_pose_model.pt
artifacts\wi-pose\metadata.json
```

Project file structure
```text
WiPose/
├──Wi-Pose
│   ├──Test
│   └──Train
├──artifacts
│   ├──wi-pose/wi_pose_model.pt
│   └──wi-pose/metadata.json
├──.gitignore
├──README.md
├──requirements.txt
└──train.py

```