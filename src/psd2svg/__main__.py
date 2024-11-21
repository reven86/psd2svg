# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import argparse
import logging
import os
from psd2svg import psd2svg

def main():
    parser = argparse.ArgumentParser(description='Convert PSD file to SVG')
    parser.add_argument(
        'input', metavar='INPUT', type=str, help='Input PSD file path or URL')
    parser.add_argument(
        'output', metavar='PATH', type=str, nargs='?', default='.',
        help='Output file or directory. When directory is specified, filename'
             ' is automatically inferred from input')
    parser.add_argument(
        '--resource-path', metavar='PATH', type=str, default=None,
        help='Resource path relative to output.')
    parser.add_argument(
        '--rasterizer', metavar='METHOD', default='chromium', type=str,
        help='Specify which rasterizer to use. default chromium.')
    parser.add_argument(
        '--loglevel', metavar='LEVEL', default='WARNING',
        help='Logging level, default WARNING')
    parser.add_argument('--shapes-only', action='store_true', help='Ignore layers and mask containing pixels.')
    parser.add_argument('--compact', action='store_true', help='Optimize output svg size by storing only visible layers, skipping layer titles, etc.')
    parser.add_argument('--padding', nargs=4, type=float, help='Values to add padding: left, top, right, bottom. Can be negative to clip the output.')
    parser.add_argument('--remove-color', action='store_true', help='Remove all colors, the shape will be rendered with current color.')
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.loglevel.upper(),
                                      'WARNING'))

    prefix, ext = os.path.splitext(args.output)
    if ext.lower() in (".png", ".jpg", ".jpeg", ".gif" ".tiff"):
        from psd2svg.rasterizer import create_rasterizer
        rasterizer = create_rasterizer(args.rasterizer)
        svg_file = prefix + ".svg"
        psd2svg(args.input, svg_file, resource_path=args.resource_path)
        image = rasterizer.rasterize(svg_file)
        image.save(args.output)
    else:
        psd2svg(args.input, args.output, resource_path=args.resource_path, shapes_only=args.shapes_only, compact=args.compact, padding=args.padding, remove_color=args.remove_color)


if __name__ == '__main__':
    main()
