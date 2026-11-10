# auto_mirror
# 🚗 Automatic Adjusting Side Mirror in Car Based on Driver's Position

<p align="center">
  <strong>An Intelligent Driver Position-Based Automatic Side Mirror Adjustment System</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.x-blue?logo=python" />
  <img src="https://img.shields.io/badge/Flask-Web%20Framework-black?logo=flask" />
  <img src="https://img.shields.io/badge/OpenCV-Computer%20Vision-green?logo=opencv" />
  <img src="https://img.shields.io/badge/MediaPipe-AI%20Vision-blue" />
</p>

## 📌 Project Overview

The **Automatic Adjusting Side Mirror System** is a computer vision-based automotive project designed to adjust car side mirrors according to the driver's position.

The system uses Python, OpenCV, MediaPipe, and Flask to process visual information and support automatic mirror positioning.

This project aims to improve driver convenience, reduce manual mirror adjustments, and provide a more personalized driving experience.

## ✨ Key Features

- 🚘 **Driver Position Detection** – Detects the driver's position using computer vision.
- 📷 **Real-Time Image Processing** – Processes camera input using OpenCV.
- 🧠 **Face Detection** – Uses MediaPipe for facial landmark detection.
- ⚙️ **Automatic Mirror Adjustment** – Supports driver-position-based mirror positioning.
- 🌐 **Flask Integration** – Provides a web-based application interface.
- 📊 **Image Processing** – Uses NumPy for numerical and image-related operations.

## 🛠️ Technologies Used

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| Flask | Web application framework |
| OpenCV | Image processing and computer vision |
| MediaPipe | Face detection and landmark tracking |
| NumPy | Numerical and array operations |

## ⚙️ System Working Process

1. The camera captures the driver's position.
2. OpenCV processes the captured image.
3. MediaPipe identifies facial landmarks.
4. Python processes the detected position information.
5. The system determines the required mirror position.
6. The mirror adjustment mechanism can use the calculated position to adjust the mirror.

## 📦 Project Dependencies

The project uses the following Python libraries:

```txt
flask>=2.3.0
opencv-python>=4.8.0
mediapipe>=0.10.0
numpy>=1.24.0
```

## 🚀 Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/kboopathiraj06-pixel/auto_mirror.git
```

### 2. Navigate to the Project Folder

```bash
cd auto_mirror
```

### 3. Create a Virtual Environment

```bash
python -m venv venv
```

### 4. Activate Virtual Environment

**Windows:**

```bash
venv\Scripts\activate
```

### 5. Install Required Libraries

```bash
pip install -r requirements.txt
```

### 6. Run the Application

```bash
python app.py
```

*Note: Use the actual Python entry-point filename in your project if it is different from `app.py`.*

## 🎯 Project Objectives

- Develop an intelligent automatic side mirror adjustment system.
- Detect driver position using computer vision.
- Reduce manual mirror adjustment.
- Improve driver comfort and convenience.
- Explore AI and automation in automotive applications.

## 🔮 Future Enhancements

- AI-based driver position estimation.
- Multiple driver profile recognition.
- Memory-based mirror adjustment.
- Integration with vehicle control systems.
- Improved mirror positioning accuracy.

## ⚠️ Disclaimer

This project is developed for educational and demonstration purposes. It is a prototype and should not be considered a certified automotive safety system. Actual vehicle integration requires appropriate engineering and safety validation.

## 🔗 Project Repository

**GitHub:** [Automatic Adjusting Side Mirror Project](https://github.com/kboopathiraj06-pixel/auto_mirror)

## 👨‍💻 Author

**Boopathiraj K**

Computer Science and Engineering

---

<p align="center">
  ⭐ If you find this project interesting, consider giving this repository a star!
</p>

<p align="center">
  <strong>Built with Python, Flask, OpenCV, MediaPipe & NumPy.</strong>
</p>
