#!/usr/bin/env python

from gimpfu import *
from math import pow, sqrt
from gimpcolor import RGB

def euclidean_distance(point_one, point_two):
    """ Calculate the euclidean distance.

        Args:
            point_one (tuple)
            point_two (tuple)

        Returns:
            float: the distance between the two points
    """
    return sqrt(pow(point_two[0] - point_one[0], 2) + \
        pow(point_two[1] - point_one[1], 2))


def get_maximum_distance(ref_list, dev_list):
    """ Calculate the distance between two list of pixels

        Args:
            ref_list (list)
            dev_list (list)

        Returns:
            float: the distance between the two list
            tuple: the pixel of the dev_list
            tuple: the pixel of the ref_list
    """

    gimp.progress_init("Calculating distance...")

    ref_pixel = (0, 0)
    dev_pixel = (0, 0)
    maximum_distance = float("-inf")
    for index, pixel_ref_list in enumerate(ref_list):
        # Update the progress bar
        gimp.progress_update(float(index) / float(len(ref_list)))

        minimum_distance = float("inf")
        for pixel_dev_list in dev_list:
            distance = euclidean_distance(pixel_ref_list, pixel_dev_list)

            # Update the minimum distance
            if distance < minimum_distance:
                minimum_distance = distance
                dev_pixel = pixel_dev_list

        # Update the maximum distance
        if minimum_distance > maximum_distance:
            maximum_distance = minimum_distance
            ref_pixel = pixel_ref_list

    return maximum_distance, dev_pixel, ref_pixel


def search_pixel(layer, color, pixel, outline_pixels):
    """ Search the outline pixels with a DFS

        Args:
            layer (gimp.Drawable): the layer over do the search
            color (gimpcolor.RGB): the outline pixel's color
            pixel (tuple): the pixel to control and from start a new search
            outline_pixels (list): the list of the outline pixels

        Returns:
            list: the list of the outline pixels
    """

    # I use a `try except` to avoid exceptions that can araise
    # if the method goes through an illegal position in the
    # image (e.g. a pixel that does not exists)
    try:
        # Goes on in the search if the color that it has met is the target color
        if RGB(*layer.get_pixel(pixel)) == color:
            outline_pixels.append(pixel)
            target_pixels = [
                (pixel[0], pixel[1] + 1), # Up
                (pixel[0] + 1, pixel[1]), # Right
                (pixel[0], pixel[1] - 1), # Down
                (pixel[0] + 1, pixel[1])  # Left
            ]

            # Searching
            for target_pixel in target_pixels:
                if target_pixel not in outline_pixels:
                    outline_pixels = search_pixel(layer, color, target_pixel, \
                        outline_pixels)
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

    # Clear an eventually selection
    pdb.gimp_selection_clear(image)

    # Initially i search the first pixel colored with the target color
    target_pixel = (0, 0)
    found_pixel = False
    for x in range(layer.width):
        gimp.progress_update(float(x) / float(layer.width))
        for y in range(layer.height):
            if RGB(*layer.get_pixel(x, y)) == color:
                target_pixel = (x, y)
                found_pixel = True

        # If the target color is found, then stop the search
        if found_pixel:
            break

    # Selecting the target area
    pdb.gimp_image_select_contiguous_color(image, 0, layer, \
        target_pixel[0], target_pixel[1])

    # Shrink the selection
    pdb.gimp_selection_shrink(image, 1)

    # Set the target color in the palette
    pdb.gimp_context_set_foreground(RGB(
        fill_color.r if fill_color.r < 1.0 else fill_color.r / 255.0,
        fill_color.g if fill_color.g < 1.0 else fill_color.g / 255.0,
        fill_color.b if fill_color.b < 1.0 else fill_color.b / 255.0,
        fill_color.a if fill_color.a < 1.0 else fill_color.a / 255.0
    ))

    # Fill the selection with the target color
    pdb.gimp_edit_bucket_fill(layer, 0, 0, 100, 0, False, 0, 0)

    gimp.progress_init("Saving the outline pixels...")
    return search_pixel(layer, color, target_pixel, [])


def hausdorff_distance(image, color, fill_color):
    """ Calculate the hausdorff distance.

        Args:
            image (Image): the image to analyse
            color (RGB):

    """

    # Indicates the start of the process
    gimp.progress_init("Initializing Hausdorff distance...")

    try:
        # Outline the first layer
        ref_layer = image.layers[0]
        ref_layer_outline_pixels_positions_list = \
            get_outline_pixels_positions(image, ref_layer, color, fill_color)

        # Outline the second layer
        dev_layer = image.layers[1]
        dev_layer_outline_pixels_positions_list = \
            get_outline_pixels_positions(image, dev_layer, color, fill_color)

        # Retrieve the maxmin distance of first layer, with the two points...
        ref_layer_distance, ref_pixel_one, ref_pixel_two = \
            get_maximum_distance(ref_layer_outline_pixels_positions_list, \
                dev_layer_outline_pixels_positions_list)

        # ...and the maxmin distance and the points of the second layer.
        dev_layer_distance, dev_pixel_one, dev_pixel_two = \
            get_maximum_distance(dev_layer_outline_pixels_positions_list, \
                ref_layer_outline_pixels_positions_list)

        # Now i make the lines to point out the two distances (obviously, the
        # maximum distance will have a wider line)
        red = (255.0, 0.0, 0.0, 255.0)



        distance = max(ref_layer_distance, dev_layer_distance)
        gimp.message("The distance is: " + str(distance))
        return distance
    except Exception as e:
        gimp.message("Unexpected error: " + str(e.message))

    gimp.message("It was not possible to calculate the distance.")
    return float("-inf")


register(
    "python-fu-hausdorff-distance",
    "AISP Hausdorff distance",
    "Calculate the Hausdorff distance between two layers.",
    "Valerio Belli",
    "Valerio Belli",
    "2017",
    "Hausdorff distance",
    "",
    [
        (PF_IMAGE, "image", """The image on which we calculates Hausdorff
            distance.""", None),
        (PF_COLOR, "color", "The outline's color.", (255.0, 255.0, 255.0, 255.0)),
        (PF_COLOR, "fill_color", "The filling color", (0.0, 0.0, 0.0, 255.0))
    ],
    [
        (PF_FLOAT, "distance", "The calculated distance."),
    ],
    hausdorff_distance,
    menu="<Image>/Filters/",
)


if "__main__" == __name__:
    main()
