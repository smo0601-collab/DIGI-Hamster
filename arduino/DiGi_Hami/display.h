// LovyanGFX-Konfiguration fuer GC9A01 am ESP32-C3 (SPI2 + DMA)
#pragma once
#define LGFX_USE_V1
#include <LovyanGFX.hpp>
#include "config.h"

class LGFX : public lgfx::LGFX_Device {
  lgfx::Panel_GC9A01 _panel;
  lgfx::Bus_SPI _bus;
#if TFT_BL >= 0
  lgfx::Light_PWM _light;
#endif

 public:
  LGFX() {
    {
      auto cfg = _bus.config();
      cfg.spi_host = SPI2_HOST;
      cfg.spi_mode = 0;
      cfg.freq_write = TFT_SPI_HZ;
      cfg.freq_read = 16000000;
      cfg.spi_3wire = true;
      cfg.use_lock = true;
      cfg.dma_channel = SPI_DMA_CH_AUTO;
      cfg.pin_sclk = TFT_SCLK;
      cfg.pin_mosi = TFT_MOSI;
      cfg.pin_miso = -1;
      cfg.pin_dc = TFT_DC;
      _bus.config(cfg);
      _panel.setBus(&_bus);
    }
    {
      auto cfg = _panel.config();
      cfg.pin_cs = TFT_CS;
      cfg.pin_rst = TFT_RST;
      cfg.pin_busy = -1;
      cfg.panel_width = 240;
      cfg.panel_height = 240;
      cfg.offset_x = 0;
      cfg.offset_y = 0;
      cfg.offset_rotation = 0;
      cfg.readable = false;
      cfg.invert = TFT_INVERT;
      cfg.rgb_order = TFT_BGR;
      cfg.dlen_16bit = false;
      cfg.bus_shared = false;
      _panel.config(cfg);
    }
#if TFT_BL >= 0
    {
      auto cfg = _light.config();
      cfg.pin_bl = TFT_BL;
      cfg.invert = false;
      cfg.freq = 12000;
      cfg.pwm_channel = 0;
      _light.config(cfg);
      _panel.setLight(&_light);
    }
#endif
    setPanel(&_panel);
  }
};

extern LGFX tft;
