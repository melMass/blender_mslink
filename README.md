# Blender MSLink
![](doc/example-compressor.png)

---

## Install

This is an almost 1:1 fork of **Quixel's official Megascan Live Link** for Blender 2.80+

- Quit Blender
- Remove the official addon if installed (located in the startup folder (`MSLink`))
- Clone this repository to your addons folder
- Launch Blender and activate the Megascans addon.
- That's it, you can now send anything from Bridge.


## Why a fork ?
The initial reason was to support ACES when detected:
- **sRGB** -> Utility - sRGB - Texture
- **Linear** -> Utility - Linear - sRGB
- **Non-Color** -> Utility - Raw

### Roadmap

Now hosted on Notion [here](https://is.gd/aCA8CE)