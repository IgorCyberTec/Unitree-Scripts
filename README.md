# Unitree Robot Dog Scripts - KairWne

This repository contains the code related to the Robot Dog project. The codes are written in Brazilian Portuguese (PT-BR) and have been commented and reviewed by artificial intelligence to ensure clarity and functionality. Here, you will find both the main application and additional scripts organized by specific functionalities.

## Repository Structure

- **[Main Application](#main-application)**: Responsible for activating the web interface and managing core functionalities.
- **Auxiliary Scripts**: Divided into categories:
  - **[Artificial Intelligence (AI)](#artificial-intelligence)**
  - **[Others](#others)**
  - **[Keyboard](#keyboard)**
  - **[Joystick](#joystick)**

---

## Main Application

The main application serves as the foundation of the Robot Dog system. It activates a web interface for control and monitoring.

### How to Run the Main Application

1. Ensure all dependencies are installed. Refer to the `requirements.txt` file for details.
2. Run the following command from the project root:
   ```bash
   cd scripts
   python app.py
   ```
3. Access the web interface in your browser at `http://localhost:8000` (or the port specified in the code).

---

## Auxiliary Scripts

Additional scripts are organized into subfolders based on their functionalities:

### Artificial Intelligence

- Location: `scripts/ia/`
- Functions: Contains algorithms related to AI.
- Execution: Ensure models are properly configured and trained if necessary before use.

### Others

- Location: `scripts/outros/`
- Functions: Miscellaneous scripts that do not fit into other categories. May include utilities or specific tests.

### Keyboard

- Location: `scripts/teclado/`
- Functions: Scripts enabling robot control using the keyboard.
- Execution: Requires the installation of keyboard event capture libraries (e.g., `pynput`).

### Joystick

- Location: `scripts/joystick/`
- Functions: Scripts to control the robot using joystick devices.
- Configuration: May require adjustments depending on the joystick model used.

---

## Important Note

For the scripts to work perfectly, the `scripts` folder must be placed in the root of the repository at the following GitHub link: [https://github.com/legion1581/go2_webrtc_connect](https://github.com/legion1581/go2_webrtc_connect).

---

## Dependencies

Ensure you install the dependencies listed in `requirements.txt` before running any code:

```bash
pip install -r requirements.txt
```

---

## Contribution

If you wish to contribute to the project:

1. Fork this repository.
2. Make the desired changes in a new branch.
3. Submit a pull request with a detailed explanation of the changes.

---

## License

This project is licensed under the terms of the [MIT License](LICENSE).

---

## Contact

For questions or suggestions, contact us at: `avasolucoesia@gmail.com`.

