#!/usr/bin/env python

import os
import sys
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
            ref_list (list): the list of points of the reference layer
                             (i.e. the layer on which we do the sup inf)
            dev_list (list): the list of points of the other level

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


def search_outline_pixels(layer, color, pixel, from_pixel, outline_pixels):
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

            # Removes the pixel from which the search comes
            for p in target_pixels:
                if p == from_pixel:
                    target_pixels.remove(p)

            # Searching
            for target_pixel in target_pixels:
                if target_pixel not in outline_pixels:
                    outline_pixels = search_outline_pixels(
                        layer, color, target_pixel, pixel, outline_pixels)
            return outline_pixels
        else:
            return outline_pixels
    except Exception as e:
        gimp.message("Raised exception while saving the outline pixels: " + \
            str(e.message))
    finally:
        return outline_pixels

def are_pixels_connected(layer, color, pixel, from_pixel, starting_pixel,
                         target_pixel, already_controlled_pixels):
    """ Checks if there is a path colored with `color` that connects
        the `starting_pixel` to the `target_pixel` with a DFS.

        Args:
            layer (gimp.Drawable): the layer over do the search
            color (gimpcolor.RGB): the outline pixel's color
            pixel (tuple): the pixel to control now
            from_pixel (tuple): the pixel from the search come
            starting_pixel (tuple): the pixel from the search starts
            target_pixel (tuple): the pixel to search
            outline_pixels (list): the list of the outline pixels

        Returns:
            `True` if the `target_pixel` are connected by an outline
            with the `starting_pixel`, otherwise False
    """

    # Uses a `try except` to avoid exceptions that can arise
    # if the method goes through an illegal position in the
    # image (e.g. a pixel that does not exists)
    try:
        # Goes on in the search if the color encountered is the target color
        if RGB(*layer.get_pixel(pixel)) == color:
            if pixel == target_pixel and from_pixel is not None:
                return True
            elif pixel == starting_pixel and from_pixel is not None:
                return False
            else:
                already_controlled_pixels.append(pixel)
                target_pixels = [
                    (pixel[0], pixel[1] + 1),  # Up
                    (pixel[0] + 1, pixel[1]),  # Right
                    (pixel[0], pixel[1] - 1),  # Down
                    (pixel[0] - 1, pixel[1])  # Left
                ]

                # Remove the pixel from which the search comes
                for p in target_pixels:
                    if p == from_pixel:
                        target_pixels.remove(p)

                # Searching
                discovered = False
                for pixel_to_control in target_pixels:
                    if pixel_to_control not in already_controlled_pixels:
                        discovered |= are_pixels_connected(
                            layer, color, pixel_to_control, pixel, starting_pixel,
                            target_pixel, already_controlled_pixels)
                return discovered
        else:
            return False
    except Exception as e:
        gimp.message("Raised exception while saving the outline pixels: " + \
                     str(e.message))


def first_discovered_pixel(layer, color, x1, y1, x2, y2):
    """ Discovers and returns the first pixel of an element
        contained in the image.

        Args:
            layer (gimp.Drawable): the layer to analyze
            color (gimpcolor.RGB): the color to discover
            x1 (int): x coordinate
            y1 (int): y coordinate
            x2 (int): x coordinate
            y2 (int): y coordinate

        Returns:
            A tuple containing the coordinates of the
            first pixel discovered
    """
    target_pixel = (0, 0)
    found_pixel = False

    # Calculates the direction on the abscissa.
    # If x1 < x2 then the direction is left to right, otherwise is right to left
    direction_on_abscissa = range(x1, x2 + 1) if x1 < x2 else range(x1, x2 - 1, -1)

    # Calculates the direction on the abscissa.
    # If y1 < y2 then the direction is up to down, otherwise is down to right
    direction_on_ordinate = range(y1, y2 + 1) if y1 < y2 else range(y1, y2 - 1, -1)

    for x in direction_on_abscissa:
        gimp.progress_update(float(x) / float(layer.width))
        for y in direction_on_ordinate:
            if RGB(*layer.get_pixel(x, y)) == color:
                target_pixel = (x, y)
                found_pixel = True

        # If the target color is found, then stops the search
        if found_pixel:
            break

    return target_pixel

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

    # Firstly retrieves the bounding box of the area of interest
    pdb.gimp_image_select_color(image, 0, layer, color)
    no_null_selection, x1, y1, x2, y2 = pdb.gimp_selection_bounds(image)

    # Initially searches the first pixel colored with the target color
    target_pixels = []

    # Searches left to right, up and down
    target_pixels.append(first_discovered_pixel(layer, color, x1, y1, x2, y2))

    # Searches right to left, up and down
    target_pixels.append(first_discovered_pixel(layer, color, x2, y1, x1, y2))

    # Searches left to right, down to up
    target_pixels.append(first_discovered_pixel(layer, color, x1, y2, x2, y1))

    # Searches right to left, down to up
    target_pixels.append(first_discovered_pixel(layer, color, x2, y2, x1, y1))

    for target_pixel in target_pixels:

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

    # Previous returns the outline pixels, controls if there is only
    # one element in the image
    for target_pixel in target_pixels:
        for other_pixel in target_pixels:
            if target_pixel != other_pixel:
                if not are_pixels_connected( layer, color,
                        target_pixel, None, target_pixel,
                        other_pixel, []):
                    raise Exception("There are disconnected elements in the image.")


    # Clears an eventual selection on the image
    pdb.gimp_selection_clear(image)

    gimp.progress_init("Saving the outline pixels...")

    return search_outline_pixels(layer, color, target_pixels[0], None, [])

def draw_line(layer, target_points, other_points):
    """ Draws a line in the layer between the two set of points

        Args:
            layer (gimp.Drawable): the layer that will be drawn
            target_points (list): the points of the biggest distance
            other_points (list): the points of the smallest distance

        Returns:
            Nothing
    """
    # Now it does the line to point out the maximum distance
    red = (1.0, 0.0, 0.0, 1.0)
    green = (0.0, 1.0, 0.0, 1.0)

    # Draws the line that connects the two couples of points
    pdb.gimp_context_set_foreground(RGB(*green))
    pdb.gimp_context_set_brush_size(2)
    pdb.gimp_pencil(layer, 4,
                    [target_points[0][0], target_points[0][1], target_points[1][0], target_points[1][1]])
    pdb.gimp_context_set_brush_size(1)
    pdb.gimp_pencil(layer, 4,
                    [other_points[0][0], other_points[0][1], other_points[1][0], other_points[1][1]])

    # Draws the points that are most distant between the two couples
    pdb.gimp_context_set_foreground(RGB(*red))
    pdb.gimp_context_set_brush_size(2)
    pdb.gimp_pencil(layer, 2, [target_points[0][0], target_points[0][1]])
    pdb.gimp_pencil(layer, 2, [target_points[1][0], target_points[1][1]])

    # Draws the other two points
    pdb.gimp_context_set_brush_size(1)
    pdb.gimp_pencil(layer, 2, [other_points[0][0], other_points[0][1]])
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

    # Increases the recursion limit of python,
    # due to it's limit of 1000 recursion call
    sys.setrecursionlimit(1000000)

    # Indicates the start of the process
    gimp.progress_init("Initializing Hausdorff distance...")

    try:
        # Calculates the numbers of images saved in the specified directory
        numbers_of_images = len([name for name in os.listdir(path) \
            if '.png' in name and 'a' in name])
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
            try:
                ref_layer_outline_pixels_positions = get_outline_pixels_positions(
                    base_image, ref_layer, color, fill_color)
            except Exception as e:
                # Writes the results
                with open("%s/results.csv" % path_to_result_file, 'a') as file:
                    file.write("A%d;B%d;%s\n" % (index, index, e.message))
                continue

            try:
                # Creates the outline of the deviated layer
                dev_layer_outline_pixels_positions = get_outline_pixels_positions(
                    base_image, dev_layer, color, fill_color)
            except Exception as e:
                # Writes the results
                with open("%s/results.csv" % path_to_result_file, 'a') as file:
                    file.write("A%d;B%d;%s\n" % (index, index, e.message))
                continue

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

            distance = 0.0
            if ref_layer_distance >= dev_layer_distance:
                distance = ref_layer_distance
                draw_line(merged_layer, [ref_pixel_one, ref_pixel_two], [dev_pixel_one, dev_pixel_two])
            else:
                distance = dev_layer_distance
                draw_line(merged_layer, [dev_pixel_one, dev_pixel_two], [ref_pixel_one, ref_pixel_two])

            # Inserts the text layer
            pdb.gimp_context_set_foreground(RGB(1.0, 1.0, 1.0, 1.0))
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
            saved.""", '/Users/valerio/PycharmProjects/Distanza di Hausdorff/images'),
        (PF_COLOR, "color", "The outline's color.", gimpcolor.RGB(*(1.0, 1.0, 1.0, 1.0))),
        (PF_COLOR, "fill_color", "The filling color", gimpcolor.RGB(*(0.0, 0.0, 0.0, 1.0))),
        (PF_DIRNAME, "path_to_result_file", """The path of the CSV file how to
            save the results distances""", '/Users/valerio/PycharmProjects/Distanza di Hausdorff')
    ],
    [],
    hausdorff_distance,
    menu="<Image>/Filters/",
)


if "__main__" == __name__:
    main()
