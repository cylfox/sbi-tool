# psx-sbi-downloader

Automatically downloads and renames [LibCrypt](https://red-j.github.io/Librehomme/libcrypt/libcrypt.html) SBI files for your PSX game collection.

The tool identifies each CHD file by reading its track layout via `chdman` and matching it against [DuckStation's](https://github.com/stenzek/duckstation) disc database to obtain the serial number. It then checks if that serial requires a LibCrypt SBI file and, if so, downloads it from [psxdatacenter.com](https://psxdatacenter.com/sbifiles.html), extracts it, and renames it to match your CHD filename so your emulator picks it up automatically.

## How it works

```
CHD file → chdman info → track sizes → discdb.yaml lookup → serial number → SBI database → download .7z → extract .sbi → rename to match CHD
```

## Requirements

- **Python 3.8+**
- **Python packages:** `pip install pyyaml requests py7zr`

External dependencies (`chdman.exe` and `discdb.yaml`) are **downloaded automatically** on first run.

## Usage

```bash
# Preview what would be downloaded (no changes made)
py sbi_downloader.py "H:\ROMs\psx" --dry-run

# Download and rename SBI files
py sbi_downloader.py "H:\ROMs\psx"
```

## Example output

```
[Dino Crisis (Spain).chd]
  Serial: SLES-02211 (Dino Crisis (Spain))
  Downloading: https://psxdatacenter.com/sbifiles/Dino%20Crisis%20(S)%20[SLES-02211]%20sbi.7z
  SAVED: Dino Crisis (Spain).sbi

[Final Fantasy VIII (Spain) (Disc 1).chd]
  Serial: SLES-02084 (Final Fantasy VIII (Spain) (Disc 1))
  Downloading: https://psxdatacenter.com/sbifiles/Final%20Fantasy%20VIII%20(S)%20[SLES-02084]%20sbi.7z
  SAVED: Final Fantasy VIII (Spain) (Disc 1).sbi
```

## What is LibCrypt?

LibCrypt was a copy protection system used on some PAL PlayStation games. Emulators need SBI files to handle the protection correctly, otherwise the game may hang, crash, or behave unexpectedly. The SBI file must share the same base filename as the disc image for the emulator to detect it.

## Notes

- **Fan-translated or patched ROMs** will not be identified since their track data differs from the official disc database. These games generally don't need SBI files anyway (LibCrypt was PAL-only).
- **Multi-disc games** (e.g., Final Fantasy VIII/IX, Parasite Eve II) are handled automatically — each disc gets its own correctly matched SBI file.
- Existing SBI files are skipped, so the tool is safe to run multiple times.

## Credits

- SBI files sourced from [psxdatacenter.com](https://psxdatacenter.com/sbifiles.html)
- Disc identification powered by [DuckStation's](https://github.com/stenzek/duckstation) game database (CC BY-NC-ND 4.0)
- CHD metadata read via [MAME's](https://www.mamedev.org/) `chdman` (GPL-2.0+), downloaded from [namDHC](https://github.com/umageddon/namDHC)
