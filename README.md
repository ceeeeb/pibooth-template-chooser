# pibooth-template-chooser

Pibooth plugin letting guests choose the picture template on the wait screen.

A banner at the top of the wait screen shows the current template, its thumbnail
and its position in the list. Guests change it by swiping horizontally on the
screen, with the `<` `>` touch buttons of the banner, or with the arrow keys.
The chosen template is used for the next pictures.

Once a picture has been taken, the wait screen shows its captures assembled
again in the selected template, so guests see the result with real photos.
The saved and printed picture is not changed.

The templates are the draw.io files of the
[pibooth-picture-template](https://github.com/pibooth/pibooth-picture-template)
plugin, which must be installed (with `pip install --no-deps` to keep the
pibooth fork).

## Configuration

```ini
[TEMPLATE_CHOOSER]
# Directory of the picture templates guests choose from on the wait screen
directory = ~/.config/pibooth/templates
```

Every `*.xml` file of the directory is offered. The template set in
`[PICTURE] template` is selected at startup when it belongs to the directory.

## Template style

A template may come with a style file of the same name (`hollywood.xml` and
`hollywood.cfg`) giving the name displayed in the banner and the style of the
texts, which replaces the `[PICTURE]` values while the template is selected:

```ini
[TEMPLATE]
name = Hollywood
text_colors = ((255, 255, 255), (230, 200, 205))
text_fonts = ('../fonts/Montserrat-Bold.ttf', '../fonts/Montserrat-SemiBold.ttf')
text_alignments = center
```

Relative font paths are resolved from the style file directory. Without a
style file, the name comes from the file name and the `[PICTURE]` style is kept.

The texts themselves (`footer_text1`, `footer_text2`) stay in `pibooth.cfg`,
shared by all the templates of an event.
