# AquaFlower Home Assistant Integration

The **AquaFlower** integration allows you to control and monitor your AquaFlower smart irrigation system directly from **Home Assistant**. With this integration, you can manage multiple irrigation zones, set timers, and see daily watering statistics.

> **Important:** You must set up and pair your AquaFlower device to the **AquaFlower Cloud** using the **AquaFlower App** before configuring this integration in Home Assistant.

---

## Installation

### **Step 1: Install via HACS (Recommended)**
1. Go to **HACS > Integrations** in Home Assistant.
2. Click **"Explore & Download Repositories"**.
3. Search for **AquaFlower** and click **"Download"**.
4. Restart Home Assistant.

### **Step 2: Manual Installation (Use Only If You Skipped Step 1)**
1. Download the latest release from [GitHub Releases](https://github.com/theaquaflower/aquaflower-home-assistant).
2. Extract and copy the `aquaflower` folder into:/config/custom_components/
3. Restart Home Assistant.

---

## Configuration

1. **Go to Home Assistant > Integrations** and click **"Add Integration"**.
2. Search for **AquaFlower** and select it.
3. Enter your **AquaFlower account email and password** (the same credentials used in the AquaFlower mobile app).
4. Enter your **Home Assistant server IP address** (e.g., `192.168.X.X`).
5. Click **Submit** to complete the setup.

---

## Device Selection  

Once you've entered your credentials and Home Assistant server IP:  

1. **Select the devices** you want to import from the list that appears.  
2. Click **Submit** to create the corresponding entities in Home Assistant.  
3. Your selected AquaFlower devices will now be available for control and monitoring within Home Assistant.  

---

## Features  

- 🌱 **Control irrigation zones** (Turn on/off).  
- ⏳ **Set irrigation timers** via Home Assistant.  
- 📊 **Real-time sync between the AquaFlower app and Home Assistant for irrigation control and monitoring.**  

---

## Troubleshooting  

### **1. Authentication Failed**  
- Ensure you’re using the **same email and password** as in the **AquaFlower mobile app**.  
- If you forgot your password, reset it through the app.  

### **2. Device Not Found**  
- Double-check that your AquaFlower device is **on and showing a green light**.  
- If the light is not green, hold the **reset button for 10 seconds**, then **re-pair the device through the AquaFlower App**.  
- Ensure that your Home Assistant **server IP** is entered correctly.  

### **3. Logs & Debugging**  
If you're experiencing issues, check the logs:  
1. Go to **Settings > System > Logs**.  
2. Search for `"aquaflower"` errors.  
3. If needed, enable **debug logging** through the integration page.  

---

## Reporting Issues  

If you encounter any issues or need help, please report them using the **GitHub Issue Tracker**:  
➡️ [AquaFlower Home Assistant Integration Issues](https://github.com/theaquaflower/AquaFlower_HA_Integration/issues)  

### **When submitting an issue, please include:**  
- A clear description of the problem.  
- Steps to reproduce the issue.  
- Any relevant Home Assistant logs.  
- Your Home Assistant version and integration version.  

Your feedback helps improve the integration! 🚀
