# pibooth-template-chooser

Pibooth plugin letting guests choose the picture template on the wait screen.

The wait screen shows the selected template in place of the last picture:
the first capture of the last picture assembled again in the single photo page
of the template, or grey photo holders until a picture exists. A discreet
caption at the top gives its name and position in the list. Guests change the
template by swiping horizontally on the screen, by tapping the `<` `>` arrows
of the caption, or with the arrow keys. The chosen template is used for the
next pictures; the saved and printed picture is not changed.

The templates are draw.io files, drawn as for the
[pibooth-picture-template](https://github.com/pibooth/pibooth-picture-template)
plugin, whose code this plugin now includes: uninstall it
(`pip uninstall pibooth-picture-template`), both declare `[PICTURE] template`.

## Configuration

```ini
[PICTURE]
# Picture template path (draw.io file), empty for the standard layout
template =

[TEMPLATE_CHOOSER]
# Directory of the picture templates guests choose from on the wait screen
directory = ~/.config/pibooth/templates
```

Every `*.xml` file of the directory is offered. The template set in
`[PICTURE] template` is selected at startup when it belongs to the directory.

## Template style

A template may come with a style file of the same name (`hollywood.xml` and
`hollywood.cfg`) giving the name displayed in the caption and the style of the
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

## Tests

```bash
pip install pytest
SDL_VIDEODRIVER=dummy pytest
```

## License

GPLv3, as the picture template code comes from
[pibooth-picture-template](https://github.com/pibooth/pibooth-picture-template)
by Vincent Verdeil and Antoine Rousseaux.

