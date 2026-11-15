#!/usr/bin/env python3
"""Render a labelled design-priority sketch, never a measured attention heatmap.

Input regions are DOM rectangles plus manually assigned weights. No behavior is collected.
"""
import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshot', type=Path, required=True)
    parser.add_argument('--regions', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    image = mpimg.imread(args.screenshot)
    data = json.loads(args.regions.read_text())
    height, width = image.shape[:2]
    xx, yy = np.meshgrid(np.arange(width), np.arange(height))
    heat = np.zeros((height, width), dtype=float)
    for region in data['regions']:
        if region['height'] <= 0:
            continue
        sx = width / data['width']
        sy = height / data['height']
        cx = (region['x'] + region['width'] / 2) * sx
        cy = (region['y'] + region['height'] / 2) * sy
        dx = max(28, min(region['width'] * sx * .45, width * .16))
        dy = max(24, min(region['height'] * sy * .45, height * .13))
        heat += region['weight'] * np.exp(-.5 * (((xx - cx) / dx)**2 + ((yy - cy) / dy)**2))
    heat = np.clip(heat, 0, 1)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'text.color': '#f5f6fa', 'axes.titlecolor': '#f5f6fa'})
    fig, axes = plt.subplots(1, 2, figsize=(22, 10), facecolor='#10131a')
    for axis in axes:
        axis.imshow(image)
        axis.axis('off')
    axes[0].set_title('CineMatch — revised homepage', fontsize=17, pad=16)
    axes[1].set_title('Design-priority sketch — NOT user measurements', fontsize=17, pad=16)
    overlay = axes[1].imshow(heat, cmap='inferno', vmin=0, vmax=1, alpha=np.clip(heat * .7, 0, .7))
    colorbar_axis = fig.add_axes([.94, .23, .012, .55])
    colorbar = fig.colorbar(overlay, cax=colorbar_axis)
    colorbar.set_label('Designer-assigned relative priority', color='#d4d8e2', fontsize=11)
    colorbar.ax.tick_params(colors='#d4d8e2')
    fig.suptitle('A hypothesis to test: clear action → compelling artwork → browsable films', fontsize=20, y=.97)
    fig.text(.5, .045, 'Manual region weights + Gaussian overlays. No eye tracking, click data, gaze probability or measured engagement uplift.',
             ha='center', color='#d4d8e2', fontsize=12)
    fig.text(.5, .018, 'Movie artwork: TMDB. Validate with task completion, time to first recommendation, errors and real participant observation.',
             ha='center', color='#b8bdca', fontsize=11)
    fig.subplots_adjust(left=.025, right=.915, top=.89, bottom=.10, wspace=.06)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(args.output)


if __name__ == '__main__':
    main()
