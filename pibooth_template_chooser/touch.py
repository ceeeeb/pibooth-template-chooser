# -*- coding: utf-8 -*-

"""Caption of the wait screen and template selection by keys and touches."""

import math

import pygame

from pibooth.utils import get_event_pos

CAPTION_HEIGHT_RATIO = 0.07
# A horizontal move longer than this share of the screen width is a swipe
SWIPE_RATIO = 0.08
# A touch moving less than this share of the screen width is a tap
TAP_RATIO = 0.03
PREVIOUS_KEYS = (pygame.K_UP, pygame.K_LEFT)
NEXT_KEYS = (pygame.K_DOWN, pygame.K_RIGHT)


class Caption(object):

    """Discreet label at the top of the wait screen, "<  name  2/9  >": the
    picture below already shows the template. Its arrows can be tapped."""

    def __init__(self):
        self.rect = self.previous_rect = self.next_rect = None

    def draw(self, surface, chooser):
        screen = surface.get_rect()
        font = pygame.font.Font(None, int(screen.height * CAPTION_HEIGHT_RATIO))
        text = font.render("{}   {}/{}".format(chooser.current.name, chooser.index + 1, len(chooser.choices)),
                           True, (255, 255, 255))
        arrow_width = text.get_height() * 2
        self.rect = pygame.Rect(0, 0, text.get_width() + 2 * arrow_width, int(text.get_height() * 1.5))
        self.rect.midtop = (screen.centerx, int(screen.height * 0.02))
        self.previous_rect = pygame.Rect(self.rect.left, self.rect.top, arrow_width, self.rect.height)
        self.next_rect = pygame.Rect(self.rect.right - arrow_width, self.rect.top, arrow_width, self.rect.height)

        background = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        pygame.draw.rect(background, (0, 0, 0, 150), background.get_rect(), border_radius=self.rect.height // 2)
        surface.blit(background, self.rect.topleft)
        surface.blit(text, text.get_rect(center=self.rect.center))
        for rect, label in ((self.previous_rect, '<'), (self.next_rect, '>')):
            arrow = font.render(label, True, (255, 255, 255))
            surface.blit(arrow, arrow.get_rect(center=rect.center))

    def step_for(self, pos):
        """Return -1 or 1 if the position hits an arrow, 0 elsewhere on the
        label, None outside of it (or before it is drawn)."""
        if self.rect is None or not self.rect.collidepoint(pos):
            return None
        if self.previous_rect.collidepoint(pos):
            return -1
        return 1 if self.next_rect.collidepoint(pos) else 0


def is_touch(event):
    return (event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP) and event.button in (1, 2, 3)) \
        or event.type in (pygame.FINGERDOWN, pygame.FINGERUP)


class Swipe(object):

    """Track a touch from press to release to recognize horizontal swipes."""

    def __init__(self):
        self.start = None

    def press(self, pos):
        self.start = pos

    def release(self, pos, width):
        """Return 1 for a swipe to the left (next), -1 to the right, 0 for
        any other move, and None for a tap (or a release without press)."""
        start, self.start = self.start, None
        if start is None:
            return None
        dx, dy = pos[0] - start[0], pos[1] - start[1]
        if math.hypot(dx, dy) < width * TAP_RATIO:
            return None
        if abs(dx) < width * SWIPE_RATIO or abs(dx) < abs(dy):
            return 0
        return 1 if dx < 0 else -1


def selection_step(caption, swipe, surface, events, touch_flip=False):
    """Return the requested move in the template list (arrow keys, swipe,
    caption arrows). The touches used for it are consumed so that they trigger
    no capture, even a missed swipe; a simple tap elsewhere keeps its pibooth
    meaning. Finger positions are mirrored when ``touch_flip`` is set, as
    pibooth does."""
    step, consumed = 0, []
    for event in events:
        if event.type == pygame.KEYDOWN and event.key in PREVIOUS_KEYS + NEXT_KEYS:
            step += -1 if event.key in PREVIOUS_KEYS else 1
            consumed.append(event)
        elif is_touch(event):
            pos = get_event_pos(surface.get_size(), event, touch_flip)
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                swipe.press(pos)
                continue
            swiped = swipe.release(pos, surface.get_width())
            touched = caption.step_for(pos)
            # A missed swipe is consumed too, or pibooth would take it for a tap
            if swiped is not None or touched is not None:
                step += swiped or touched or 0
                consumed.append(event)
    for event in consumed:
        events.remove(event)
    return step
