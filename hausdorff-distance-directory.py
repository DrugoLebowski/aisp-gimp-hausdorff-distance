#!/usr/bin/env python

import os
import os.path

from gimpfu import *
from math import pow, sqrt, floor
from gimpcolor import RGB

def euclidean_distance(point_one, point_two):
    """ Calculates the euclidean distance.

        Args:
            point_one (tuple)
            point_two (tuple)

        Returns:
            float: the distance between the two points
    """
    return sqrt(pow(point_two[0] - point_one[0], 2) + \
        pow(point_two[1] - point_one[1], 2))


def get_maximum_distance(ref_list, dev_list):
    """ Calculates the distance between two list of pixels

        Args:
            ref_list (list)
            dev_list (list)

        Returns:
            float: the distance between the two list
            tuple: the pixel of the dev_list
            tuple: the pixel of the ref_list
    """

    gimp.progress_init("Calculating distance...")

    point_one = (0, 0)
    point_two = (0, 0)
    maximum_distance = 0.0
    for index, pixel_ref in enumerate(ref_list):
        # Updates the progress bar
        gimp.progress_update(float(index) / float(len(ref_list)))

        minimum_pixel = None
        minimum_distance = float("inf")
        for pixel_dev in dev_list:
            distance = euclidean_distance(pixel_ref, pixel_dev)
            if distance < minimum_distance:
                minimum_distance = distance
                minimum_pixel = pixel_dev

        # Updates the maximum distance
        if minimum_distance > maximum_distance:
            maximum_distance = minimum_distance
            point_one = pixel_ref
            point_two = minimum_pixel

    return maximum_distance, point_one, point_two


def search_pixel(layer, color, pixel, outline_pixels):
    """ Searches the outline pixels with a DFS

        Args:
            layer (gimp.Drawable): the layer over do the search
            color (gimpcolor.RGB): the outline pixel's color
            pixel (tuple): the pixel to control and from start a new search
            outline_pixels (list): the list of the outline pixels

        Returns:
            list: the list of the outline pixels
    """

    # Uses a `try except` to avoid exceptions that can arise
    # if the method goes through an illegal position in the
    # image (e.g. a pixel that does not exists)
    try:
        # Goes on in the search if the color encountered is the target color
        if RGB(*layer.get_pixel(pixel)) == color:
            outline_pixels.append(pixel)
            target_pixels = [
                (pixel[0], pixel[1] + 1), # Up
                (pixel[0] + 1, pixel[1]), # Right
                (pixel[0], pixel[1] - 1), # Down
                (pixel[0] - 1, pixel[1])  # Left
            ]

            # Searching
            for target_pixel in target_pixels:
                if target_pixel not in outline_pixels:
                    outline_pixels = search_pixel(
                        layer, color, target_pixel, outline_pixels)
    except Exception as e:
        gimp.message("Raised exception while saving the outline pixels: " + \
            str(e.message))
    finally:
        return outline_pixels


def get_outline_pixels_positions(image, layer, color, fill_color):
    """ Create the outline and search the pixels of the outline.

        Args:
            image (gimp.Image): the image over we make the transformation
            layer (gimp.Drawable): the layer we transformate
            color (gimpcolor.RGB): the outline's color
            fill_color (gimpcolor.tuple): the other color

        Returns:
            list: the list of the outline pixels
    """

    gimp.progress_init("Searching the outline pixels for the layer...")

    # Initially searches the first pixel colored with the target color
    target_pixel = (0, 0)
    found_pixel = False
    for x in range(layer.width):
        gimp.progress_update(float(x) / float(layer.width))
        for y in range(layer.height):
            if RGB(*layer.get_pixel(x, y)) == color:
                target_pixel = (x, y)
                found_pixel = True

        # If the target color is found, then stops the search
        if found_pixel:
            break

    # Selects the target area
    pdb.gimp_image_select_contiguous_color(
        image, 0, layer, target_pixel[0], target_pixel[1])

    # Shrinks the selection
    pdb.gimp_selection_shrink(image, 1)

    # Sets the target color in the palette
    pdb.gimp_context_set_foreground(RGB(
        fill_color.r if fill_color.r < 1.0 else fill_color.r / 255.0,
        fill_color.g if fill_color.g < 1.0 else fill_color.g / 255.0,
        fill_color.b if fill_color.b < 1.0 else fill_color.b / 255.0,
        fill_color.a if fill_color.a < 1.0 else fill_color.a / 255.0
    ))

    # Fills the selection with the target color
    pdb.gimp_edit_bucket_fill(layer, 0, 0, 100, 0, False, 0, 0)

    gimp.progress_init("Saving the outline pixels...")

    # Clears an eventual selection on the image
    pdb.gimp_selection_clear(image)

    return search_pixel(layer, color, target_pixel, [])

def draw_line(layer, target_points, other_points):
    """ Draws a line in the layer between the two set of points
    :param layer:
    :param target_points:
    :param other_points:
    :return:
    """
    # Now it does the line to point out the maximum distance
    red = (1.0, 0.0, 0.0, 1.0)
    green = (0.0, 1.0, 0.0, 1.0)

    # Draws a line that connects the two points
    pdb.gimp_context_set_foreground(RGB(*green))
    pdb.gimp_context_set_brush_size(2)
    pdb.gimp_pencil(layer, 4,
                    [target_points[0][0], target_points[0][1], target_points[1][0], target_points[1][1]])
    pdb.gimp_context_set_brush_size(1)
    pdb.gimp_pencil(layer, 4,
                    [other_points[0][0], other_points[0][1], other_points[1][0], other_points[1][1]])

    # Draws the points - First point
    pdb.gimp_context_set_foreground(RGB(*red))
    pdb.gimp_context_set_brush_size(2)
    pdb.gimp_pencil(layer, 2, [target_points[0][0], target_points[0][1]])
    pdb.gimp_context_set_brush_size(1)
    pdb.gimp_pencil(layer, 2, [other_points[0][0], other_points[0][1]])

    # Second point
    pdb.gimp_context_set_brush_size(2)
    pdb.gimp_pencil(layer, 2, [target_points[1][0], target_points[1][1]])
    pdb.gimp_context_set_brush_size(1)
    pdb.gimp_pencil(layer, 2, [other_points[1][0], other_points[1][1]])

def hausdorff_distance(path, color, fill_color, path_to_result_file):
    """ Calculate the hausdorff distance.

        Args:
            path (str): tha path where the images reside
            color (gimpcolor.RGB): the outline color
            fill_color (gimpcolor.RGB): the filling color
            path_to_result_file (str): the path where the `results.csv` file will be saved

        Returns:
            Nothing
    """

    # Indicates the start of the process
    gimp.progress_init("Initializing Hausdorff distance...")

    try:
        # Calculates the numbers of images saved in the specified directory
        numbers_of_images = int(floor(len([name for name in os.listdir(path) \
            if '.png' in name]) / 2))
        with open("%s/results.csv" % path_to_result_file, 'w') as file:
            file.write("Reference image;Deviated image;Distance\n")

        for index in range(1, numbers_of_images + 1):
            # Loads the reference image in memory
            base_image = pdb.file_png_load('%s/a%d.png' % (path, index), '')
            ref_layer = base_image.layers[0] # Retrieves the ref layer

            # Loads the deviated image as layer to the image
            dev_layer = pdb.gimp_file_load_layer(base_image, '%s/b%d.png' % (path, index))
            pdb.gimp_image_insert_layer(base_image, dev_layer, None, 0)

            # Creates the outline of the reference layer
            ref_layer_outline_pixels_positions = get_outline_pixels_positions(
                base_image, ref_layer, color, fill_color)
            gimp.message("Analyzed: %s, %d outline pixels"
                         % (ref_layer.name, len(ref_layer_outline_pixels_positions)))

            # Creates the outline of the deviated layer
            dev_layer_outline_pixels_positions = get_outline_pixels_positions(
                base_image, dev_layer, color, fill_color)
            gimp.message("Analyzed: %s, %d outline pixels"
                         % (dev_layer.name, len(dev_layer_outline_pixels_positions)))

            # Retrieves the maxmin distance of first layer, with the two points...
            ref_layer_distance, ref_pixel_one, ref_pixel_two = get_maximum_distance(
                ref_layer_outline_pixels_positions, dev_layer_outline_pixels_positions)

            # ...and the maxmin distance and the points of the second layer.
            dev_layer_distance, dev_pixel_one, dev_pixel_two = get_maximum_distance(
                dev_layer_outline_pixels_positions, ref_layer_outline_pixels_positions)


            # Merges the layers to point out the maximum distance
            pdb.gimp_layer_set_mode(dev_layer, 7)
            pdb.gimp_image_merge_down(base_image, dev_layer, 1)
            merged_layer = base_image.layers[0]
            pdb.gimp_layer_set_mode(merged_layer, 0)

            distance = 0.0
            if ref_layer_distance >= dev_layer_distance:
                distance = ref_layer_distance
                draw_line(merged_layer, [ref_pixel_one, ref_pixel_two], [dev_pixel_one, dev_pixel_two])
            else:
                distance = dev_layer_distance
                draw_line(merged_layer, [dev_pixel_one, dev_pixel_two], [ref_pixel_one, ref_pixel_two])

            # Inserts the text layer
            text_layer = pdb.gimp_text_layer_new(
                base_image, "Hausdorff distance: %f" % distance, "Verdana", 14, 0)
            pdb.gimp_image_insert_layer(base_image, text_layer, None, 0)
            pdb.gimp_layer_translate(text_layer, 5, 5)

            # Merging the layers
            pdb.gimp_layer_set_mode(text_layer, 7)
            pdb.gimp_image_merge_down(base_image, text_layer, 1)
            merged_layer = base_image.layers[0]

            # Saves the merged image
            pdb.gimp_file_save(base_image, merged_layer, '%s/c%d.png' % (path, index), '')

            # Writes the results
            with open("%s/results.csv" % path_to_result_file, 'a') as file:
                file.write("A%d;B%d;%f\n" % (index, index, distance))

            # Close the generated image
            pdb.gimp_image_delete(base_image)
    except Exception as e:
        gimp.message("Unexpected error: %s." % e.message)
        gimp.message("It was not possible to calculate the distance.")


register(
    "python-fu-hausdorff-dd",
    "AISP Hausdorff distance from directory",
    "Calculate the Hausdorff distance between two images loaded from a directory",
    "Valerio Belli",
    "Valerio Belli",
    "2017",
    "Hausdorff distance from directory",
    "",
    [
        (PF_DIRNAME, "path", """The path where the images to analyse are
            saved.""", None),
        (PF_COLOR, "color", "The outline's color.", gimpcolor.RGB(*(1.0, 1.0, 1.0, 1.0))),
        (PF_COLOR, "fill_color", "The filling color", gimpcolor.RGB(*(0.0, 0.0, 0.0, 1.0))),
        (PF_DIRNAME, "path_to_result_file", """The path of the CSV file how to
            save the results distances""", None)
    ],
    [],
    hausdorff_distance,
    menu="<Image>/Filters/",
)


if "__main__" == __name__:
    main()
