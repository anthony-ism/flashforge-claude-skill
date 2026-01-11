# FlashForge Adventurer 5M Printing Guidelines

## Printer Specifications

| Specification | Value |
|--------------|-------|
| Build Volume | 220 x 220 x 220 mm |
| Nozzle Diameter | 0.4 mm (standard) |
| Max Nozzle Temp | 280°C |
| Max Bed Temp | 110°C |
| Max Print Speed | 600 mm/s |
| Filament Diameter | 1.75 mm |

## Recommended Settings by Model Type

### Decorative Items (lithophanes, relief art, display pieces)

- **Layer Height:** 0.12-0.16 mm for detail
- **Infill:** 15-20%
- **Wall Count:** 2-3
- **Print Speed:** 100-150 mm/s
- **Material:** PLA

### Functional Parts (clips, brackets, mounts)

- **Layer Height:** 0.2 mm for strength
- **Infill:** 40-60%
- **Wall Count:** 4+
- **Print Speed:** 150-200 mm/s
- **Material:** PLA or PETG

### Lithophanes (Specific Settings)

- **Layer Height:** 0.12 mm
- **Infill:** 100%
- **Wall Count:** Maximum
- **Print Speed:** 50-80 mm/s (slow for quality)
- **Material:** White PLA
- **Orientation:** Print vertically for best light transmission

## Material Settings

### PLA

- Nozzle: 195-210°C
- Bed: 55-60°C
- Cooling: 100%
- Speed: Up to 200 mm/s

### PETG

- Nozzle: 230-250°C
- Bed: 70-80°C
- Cooling: 50%
- Speed: Up to 150 mm/s

### TPU (Flexible)

- Nozzle: 220-235°C
- Bed: 40-60°C
- Cooling: 50%
- Speed: 20-40 mm/s (slow required)

## Tips for 2D-to-3D Prints

### General

1. **Add a base plate** - 2mm base improves bed adhesion
2. **Use a brim** for thin features to prevent warping
3. **Orient for strength** - layer lines are weakest direction

### Heightmap Models (Photos/Art)

- Use 0.12mm layers for detail preservation
- Consider 100% infill for thin sections
- White PLA works best for lithophanes

### Contour Models (Icons/Logos)

- Increase wall count for small details
- Use supports for overhangs > 45°
- Consider printing flat for best top surface

### SVG Models (Vector Graphics)

- Simplify complex paths before conversion
- Check for self-intersecting paths
- Ensure minimum 0.8mm wall thickness for printability

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Poor bed adhesion | Bed too cool or dirty | Clean with IPA, increase bed temp |
| Warping corners | Cooling too fast | Use brim, reduce fan speed first layers |
| Stringing | Temperature too high | Reduce temp, increase retraction |
| Missing details | Layer height too large | Use 0.12mm layers, slow down |
| Weak parts | Low infill or walls | Increase infill and wall count |

## File Preparation Checklist

- [ ] Model fits within 220x220x220mm build volume
- [ ] Mesh is watertight (no holes)
- [ ] Minimum wall thickness is 0.8mm
- [ ] Base plate added for adhesion
- [ ] No unsupported overhangs > 45°
- [ ] File size is reasonable (< 100MB for slicer performance)
