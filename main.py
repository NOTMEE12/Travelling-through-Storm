# /// script
# dependencies = [
#   "math", "random", "sys", "pygame-ce",  "typing", "dataclasses", "asyncio", "json", "os", "tomllib"
# ]
# requires-python = ">=3.11"
# ///
import math
import random
from sys import exit, argv
import pygame

import WorldD_r

try:
    import WorldD_r.main as WorldD
except Exception as e:
    print(
        """









    WorldD_r.main






""",
        e,
    )


import typing
from dataclasses import dataclass
import asyncio


# pygame.init()


def outline(img: pygame.Surface, color=(255, 255, 255), width=1, corners=(True, True, True, True)):
    """
    outline an image with a color.
    :param img: image
    :type img: pygame.Surface
    :param color: color of the outline
    :type color: Sequence[int | float]
    :param width: width of the outline
    :type width: int
    :param corners: should the outline also cover corners?
    :type corners: Sequence[bool]
    :return: image with outline
    :rtype: pygame.Surface
    """
    new_img = pygame.Surface((img.get_width() + width * 2, img.get_height() + width * 2), pygame.SRCALPHA)
    cl = pygame.mask.from_surface(img.copy().convert_alpha()).to_surface(
        surface=img.copy().convert_alpha(), setcolor=color, unsetcolor=(0, 0, 0, 0)
    )
    # top
    if corners[0]:
        new_img.blit(cl, (0, 0))
    new_img.blit(cl, (width, 0))
    if corners[1]:
        new_img.blit(cl, (width * 2, 0))
    # mid
    new_img.blit(cl, (0, width))
    # middle of the middle is redundant since it will not be visible
    new_img.blit(cl, (width * 2, width))
    # bottom
    if corners[2]:
        new_img.blit(cl, (0, width * 2))
    new_img.blit(cl, (width, width * 2))
    if corners[3]:
        new_img.blit(cl, (width * 2, width * 2))

    new_img.blit(img, (width, width))
    return new_img


@dataclass
class Config:
    """Config class for tile layers"""

    TILE_LAYER = 0

    MOVE_UP = pygame.K_w
    MOVE_LEFT = pygame.K_a
    MOVE_RIGHT = pygame.K_d
    MOVE_DOWN = pygame.K_s


class World:
    def __init__(self, main, world_path, max_move_count):
        # load the world and export the most important things
        tile_size, _, self.tiles, self.grid, layer_names = WorldD.load(world_path)
        # scale the tile size
        self.tile_size = pygame.Vector2(tile_size)

        # load the sp_sheet (loading from the WorldD.load is not the best option
        # since the path will not be the same on every computer
        self.sp_sheet = main.sp_sheet

        # assign the display and main
        self.display = main.display
        self.main = main

        # setup how many tiles there will be in one row and column

        # setup caching for better performance
        self.tile_cache = {Config.TILE_LAYER: {}}
        self.block_render_pos_cache = {}

        self.move_count = 0
        self.max_move_count = max_move_count

    def get_block_pos(self, pos, offset: typing.Union[typing.Sequence[int], None] = None):
        if offset is None:
            offset = self.main.offset[0] * self.tile_size[0], self.main.offset[1] * self.tile_size[1]
        return pygame.Vector2(pos[0] - offset[0], pos[1] - offset[1]) // self.tile_size[0]

    def block_render_pos(self, grid_pos, offset: typing.Union[typing.Sequence[int], None] = None) -> tuple[int, int]:
        """
        :parameter grid_pos: position on the grid
        :parameter offset: offset of Main offset * tile size, if not given then calculated in this function.
        :returns: position where tile should be rendered based on the grid position
        """
        if tuple(grid_pos) not in self.block_render_pos_cache:
            self.block_render_pos_cache[tuple(grid_pos)] = self.tile_size.elementwise() * grid_pos
        if offset is None:
            offset = self.main.offset * self.tile_size[0]
        res = self.block_render_pos_cache[tuple(grid_pos)].copy()

        # Isometric mapping
        res.y *= 0.25
        res.x += grid_pos[1] / 2 * self.tile_size[0]
        # if grid_pos[1] % 2 == 1:
        # 	res.x += self.tile_size[0] * .5

        res = res.elementwise() + offset
        return res

    def render(self):
        offset = self.main.offset[0] * self.tile_size[0], self.main.offset[1] * self.tile_size[1]
        left, top = -int(offset[0] // self.tile_size[0]) - 1, -int(offset[1] // self.tile_size[1]) - 1
        right, bottom = (
            int(left + self.display.get_width() // self.tile_size[0]) + 2,
            int(top + self.display.get_height() // self.tile_size[1]) + 1,
        )
        bottom += 3
        # for every column visible
        for y in range(top, bottom):
            # for every row visible
            for x in range(left, right):
                # if tile doesn't exist: next loop
                if (x, y) not in self.grid[Config.TILE_LAYER]:
                    continue
                # if tile not cache:
                if (x, y) not in self.tile_cache[Config.TILE_LAYER]:
                    # gather the information about tile group and name
                    tile_group, tile_name = self.grid[Config.TILE_LAYER][(x, y)]
                    # get subsurface pos
                    tile_subsurface_pos = self.tiles[tile_group].tiles[tile_name]
                    # get texture
                    tile_texture = self.sp_sheet.subsurface(tile_subsurface_pos)
                    # scale texture
                    tile_texture = pygame.transform.scale(tile_texture, self.tile_size)
                    # cache it
                    self.tile_cache[Config.TILE_LAYER][(x, y)] = tile_texture
                else:
                    # if tile is in cache: retrieve it
                    tile_texture = self.tile_cache[Config.TILE_LAYER][(x, y)]

                # render tile
                self.display.blit(tile_texture, self.block_render_pos((x, y), offset=offset))


class Player:
    def __init__(self, main):
        self.main: Main = main
        self.grid_pos = pygame.Vector2()
        self.last_move = (0, 0)
        self.render_pos = self.main.worlds[0].block_render_pos(self.grid_pos)
        self.images = (main.sp_sheet.subsurface(16, 32, 16, 16), main.sp_sheet.subsurface(16, 16, 16, 16))
        self.offset = pygame.Vector2(0, 16) / 4
        self.ready_for_next_move = True
        self.max_health = 2
        self.__health = self.max_health

    @property
    def health(self):
        return self.__health

    @health.setter
    def health(self, value):
        self.__health = value
        if self.__health <= 0:
            self.main.death_screen.fade(255)

    def render(self):
        self.main.display.blit(self.images[max(self.health - 1, 0)], self.render_pos - self.offset)

    def update(self):
        self.move()

    def move(self):
        if self.main.current_world is None:
            return
        dest_render_pos = self.main.current_world.block_render_pos(self.grid_pos)
        self.render_pos.move_towards_ip(dest_render_pos, self.main.dt * 20)
        if self.render_pos == dest_render_pos:
            self.ready_for_next_move = True


class Entity:
    def __init__(self, main, grid_pos, image):
        self.main = main
        self.grid_pos = pygame.Vector2(grid_pos)
        self.org_grid_pos = pygame.Vector2(grid_pos)
        self.render_pos = pygame.Vector2()
        self.image = image
        self.render_offset = pygame.Vector2() / 2
        self.move_speed = 20

    def setup(self):
        self.grid_pos = self.org_grid_pos.copy()
        self.render_pos = self.main.current_world.block_render_pos(self.grid_pos)

    def draw(self):
        self.render_pos.move_towards_ip(self.main.current_world.block_render_pos(self.grid_pos), self.main.dt * self.move_speed)
        self.main.display.blit(self.image, self.render_pos + self.render_offset)

    @property
    def can_move(self):
        return self.render_pos == self.main.current_world.block_render_pos(self.grid_pos)

    def on_can_move(self):
        pass

    def move(self, direction):
        self.on_can_move()
        self.grid_pos += direction


class Shark(Entity):
    def __init__(self, main, grid_pos, direction=(0, 1)):
        self.org_image = main.sp_sheet.subsurface((32, 16, 16, 16))
        super().__init__(main, grid_pos, self.org_image)
        self.org_direction = pygame.Vector2(direction)
        if direction[0] != 0:
            self.org_image = pygame.transform.flip(self.image, True, False)
        if direction[1] != 1:
            self.org_image = pygame.transform.flip(self.image, True, False)
        self.direction = self.org_direction.copy()
        self.can_attack = False

    def setup(self):
        super().setup()
        self.direction = self.org_direction.copy()
        self.image = self.org_image.copy()

    def render(self):
        super().draw()
        if self.render_pos.distance_to(self.main.player.render_pos) <= 2 and self.can_attack:
            self.grid_pos -= self.direction
            self.main.player.health -= 1
            self.main.player.grid_pos -= self.main.player.last_move
            self.can_attack = False

    def on_can_move(self):
        if tuple(self.grid_pos + self.direction) not in self.main.current_world.grid[0]:
            print("out of the world I go")
            self.direction *= -1
            self.image = pygame.transform.flip(self.image, True, False)
        self.can_attack = True

    def update(self):
        super().move(self.direction)


class Storm(Entity):
    def __init__(self, main, grid_pos):
        super().__init__(main, grid_pos, main.sp_sheet.subsurface(0, 32, 16, 16))
        self.move_speed = 40

    def setup(self):
        self.grid_pos = self.org_grid_pos
        self.render_pos = self.main.current_world.block_render_pos(self.grid_pos) - (0, 64)

    def render(self):
        super().draw()
        if self.main.player.render_pos == self.render_pos and self.main.current_world.move_count > 0:
            self.main.player.health -= 1
            self.main.player.grid_pos += random.choice(((-1, 0), (1, 0), (0, 1), (0, -1)))

    def update(self):
        pass


class Ending:
    def __init__(self, main, image_path):
        self.image = pygame.image.load(image_path).convert()
        self.main: Main = main

    def render(self):
        self.main.display.blit(self.image, (0, 0))


class DeathScreen(Ending):
    def __init__(self, main):
        super().__init__(main, "death.png")
        self.alpha = 0
        self.dst_alpha = 0
        self.dst_speed = 2
        self.title = "You died!"
        self.title_size = 30
        self.subtitle = "Press R to restart."

    def fade(self, dst_alpha, speed=None):
        """
        fade in
        :param dst_alpha: desired alpha
        :type dst_alpha: int
        :param speed: speed [ alpha value per second ]
        :type speed: int | float
        :return:
        :rtype: None
        """
        self.dst_alpha = dst_alpha
        self.main.dst_display_alpha = 255
        if speed is not None:
            self.dst_speed = speed

    def render(self):
        self.alpha = pygame.math.lerp(self.alpha, self.dst_alpha, self.main.dt * self.dst_speed)
        if self.alpha <= 1:
            return
        self.image.set_alpha(self.alpha)

        old_size = self.main.font.point_size
        self.main.font.point_size = self.title_size
        self.main.font.align = pygame.FONT_CENTER
        title = self.main.font.render(self.title, False, self.main.text_color, wraplength=self.main.display.get_width())
        title = outline(title, self.main.text_outline)
        title.set_alpha(self.alpha)

        self.main.font.set_point_size(old_size)
        subtitle = self.main.font.render(self.subtitle, False, self.main.text_color)
        subtitle = outline(subtitle, self.main.text_outline)
        subtitle.set_alpha(self.alpha)
        subtitle_pos = pygame.Vector2(subtitle.get_rect(center=pygame.Vector2(self.main.display.get_size()) / 2).midleft)

        subtitle_pos.y += math.sin(pygame.time.get_ticks() / 600) * 4

        self.main.display.blit(title, title.get_rect(center=(self.main.display.get_width() / 2, title.get_height() / 2 + 4 * 2)))
        super().render()
        self.main.display.blit(subtitle, subtitle_pos)


class TooManyMoves(DeathScreen):
    def __init__(self, main):
        super().__init__(main)
        self.title = "Too Many Moves!"
        self.title_size = 19


class CustomWorld(World):
    def __init__(self, main, world_path, entities, max_move_count=5):
        super().__init__(main, world_path, 5)
        self.entities = entities
        self.max_move_count = max_move_count


class Fog(Entity):
    def __init__(self, main, grid_pos):
        super().__init__(main, grid_pos, main.sp_sheet.subsurface(0, 48, 16, 16))
        self.fog_color = pygame.Color("#221228")
        self.fog_points = [
            pygame.Vector2(-4, 2),
            pygame.Vector2(-2, 6),
            pygame.Vector2(-4, 4),
            pygame.Vector2(2, 4),
            pygame.Vector2(2, 6),
            pygame.Vector2(0, 8),
            pygame.Vector2(0, 0),
        ]
        self.circle = pygame.Surface((8, 8), pygame.SRCALPHA)
        pygame.draw.circle(self.circle, self.fog_color, (4, 4), 3)
        self.offset = random.random() * 10

    def setup(self):
        self.render_pos = self.main.current_world.block_render_pos(self.grid_pos)

    def render(self):
        super().draw()
        for idx, point in enumerate(self.fog_points):
            self.circle.set_alpha(math.cos(pygame.time.get_ticks() / 1000 + self.offset + idx * 200) * 64 + 128 + 80)
            dst_pos = self.render_pos + (8, 0) + point.xy
            pos = dst_pos - (3, 3)
            self.main.display.blit(self.circle, pos)
        if (self.render_pos).distance_to(self.main.player.render_pos) <= 2:
            self.main.player.health = 0

    def update(self):
        pass


class Main:
    def __init__(self):

        #self.window = pygame.Window("Travelling through Storm | ")
        #self.window.set_icon(pygame.image.load("icon.ico"))
        #self.window_surf = self.window.get_surface()
        print(420)
        self.window_surf = pygame.display.set_mode([640, 480])
        self.title = 'Travelling through Storm | '
        print(426)
        self.scale = 4

        self.display = pygame.Surface(pygame.Vector2(160, 120), pygame.SRCALPHA)
        self.display_alpha = 255
        self.dst_display_alpha = 255

        self.sp_sheet = pygame.image.load("asset-spritesheet.png").convert_alpha()
        self.cur_world_id = 0
        self.worlds = (
            CustomWorld(self, "worlds/1.world", [Shark(self, (0, 2)), Shark(self, (-1, 3))]),
            CustomWorld(
                self, "worlds/1.world", [Storm(self, (0, 1)), Storm(self, (1, 0)), Storm(self, (1, 1)), Storm(self, (-2, 2))]
            ),
            CustomWorld(
                self,
                "worlds/1.world",
                [
                    Storm(self, (-1, 0)),
                    Storm(self, (-1, 1)),
                    Shark(self, (-2, 2)),
                    Shark(self, (-1, 4)),
                    Shark(self, (-1, 1)),
                    Shark(self, (1, -1)),
                ],
            ),
            CustomWorld(
                self,
                "worlds/1.world",
                [
                    Fog(self, (-1, 1)),
                    Fog(self, (-2, 2)),
                    Fog(self, (-2, 4)),
                    Fog(self, (-1, 3)),
                    Fog(self, (-1, 4)),
                    Fog(self, (1, 0)),
                ],
                7,
            ),
            CustomWorld(
                self,
                "worlds/1.world",
                [
                    Storm(self, (-2, 3)),
                    Storm(self, (0, 1)),
                    Shark(self, (-3, 5), (0, -1)),
                    Shark(self, (-1, 2), (0, -1)),
                    Shark(self, (-2, 4), (0, -1)),
                    Shark(self, (-1, 3), (0, -1)),
                    Fog(self, (-1, 1)),
                    Fog(self, (-2, 2)),
                    Fog(self, (-2, 4)),
                    Fog(self, (-1, 3)),
                    Fog(self, (0, 2)),
                ],
                9,
            ),
            CustomWorld(
                self,
                "worlds/1.world",
                [
                    Storm(self, (0, 2)),
                    Shark(self, (1, 2)),
                    Shark(self, (-1, 2)),
                    Shark(self, (-3, 5), (0, -1)),
                    Fog(self, (-2, 2)),
                    Fog(self, (-1, 1)),
                    Fog(self, (0, 1)),
                    Fog(self, (-1, 2)),
                    Fog(self, (-1, 3)),
                    Fog(self, (-2, 4)),
                    Fog(self, (1, 2)),
                ],
                13,
            ),
            CustomWorld(
                self,
                "worlds/1.world",
                [
                    Shark(self, (1, 0)),
                    Shark(self, (1, -2)),
                    Shark(self, (-2, 5)),
                    Shark(self, (-3, 5)),
                    Fog(self, (1, -2)),
                    Fog(self, (0, -1)),
                    Fog(self, (-2, 2)),
                    Fog(self, (-2, 3)),
                    Fog(self, (-1, 2)),
                    Fog(self, (0, 1)),
                    Fog(self, (0, 2)),
                    Fog(self, (-1, 3)),
                ],
                11,
            ),
            CustomWorld(
                self,
                "worlds/1.world",
                [
                    Storm(self, (0, 2)),
                    Storm(self, (-2, 4)),
                    Shark(self, (-1, 1), (-1, 1)),
                    Shark(self, (-3, 5)),
                    Shark(self, (1, -2)),
                    Fog(self, (1, -2)),
                    Fog(self, (-1, 0)),
                    Fog(self, (-3, 2)),
                    Fog(self, (0, 1)),
                    Fog(self, (-1, 2)),
                    Fog(self, (-2, 3)),
                    Fog(self, (-1, 3)),
                    Fog(self, (1, 2)),
                ],
                9,
            ),
            CustomWorld(
                self,
                "worlds/1.world",
                [
                    Shark(self, (0, -1)),
                    Shark(self, (-2, 3)),
                    Shark(self, (-2, 5)),
                    Shark(self, (-3, 3)),
                    Fog(self, (1, -2)),
                    Fog(self, (1, -1)),
                    Fog(self, (1, 0)),
                    Fog(self, (1, 1)),
                    Fog(self, (1, 2)),
                    Fog(self, (-1, 2)),
                    Fog(self, (-2, 3)),
                    Fog(self, (-1, 3)),
                    Fog(self, (-2, 1)),
                    Fog(self, (-3, 2)),
                ],
                5,
            ),
            CustomWorld(
                self,
                "worlds/9.world",
                [
                    Shark(self, (-2, 4), (-1, 1)),
                    Shark(self, (-3, 4), (0, -1)),
                    Fog(self, (1, -2)),
                    Fog(self, (1, -1)),
                    Fog(self, (1, 0)),
                    Fog(self, (0, 1)),
                    Fog(self, (-2, 2)),
                    Fog(self, (-2, 2)),
                    Fog(self, (-2, 3)),
                    Fog(self, (-2, 4)),
                ],
                8,
            ),
            CustomWorld(
                self,
                "worlds/9.world",
                [
                    Shark(self, (1, -1), (0, 1)),
                    Shark(self, (1, -1), (0, -1)),
                    Shark(self, (0, -1)),
                    Shark(self, (-1, 4), (0, -1)),
                    Fog(self, (1, -2)),
                    Fog(self, (0, -1)),
                    Fog(self, (-2, 2)),
                    Fog(self, (0, 1)),
                    Fog(self, (-1, 2)),
                    Fog(self, (-1, 3)),
                    Fog(self, (-2, 2)),
                    Fog(self, (-3, 5)),
                ],
                10,
            ),
        )
        self.offset = self.worlds[0].get_block_pos(self.display.get_size(), offset=(0, 0)).elementwise() / 2 + (0, -0.5)
        self.player = Player(self)
        self.ending = Ending(self, "ending.png")
        self.death_screen = DeathScreen(self)
        self.too_much_moves = TooManyMoves(self)
        for entity in self.worlds[self.cur_world_id].entities:
            entity.setup()

        self.dt = 0
        self.clock = pygame.Clock()
        self.FPS = 60

        self.font = pygame.font.Font("font/Lobster.ttf", 15)
        self.text_color = pygame.Color("#652654")
        self.text_outline = pygame.Color("#9e3455")
        self.background_color = pygame.Color("#221228")
        self.world_outline_color = pygame.Color("#652654")

        pygame.mixer.init(channels=1)
        self.sea_sound_channel = pygame.mixer.Channel(0)
        self.sea_sound_channel.set_volume(0.3)
        # self.player_move_sound_channel = pygame.mixer.Channel(1)
        # self.player_attacked_sound_channel = pygame.mixer.Channel(2)
        self.sea_sound = pygame.mixer.Sound("sounds/sea.ogg")

    @property
    def current_world(self) -> World | None:
        if self.cur_world_id >= len(self.worlds):
            return None
        return self.worlds[self.cur_world_id]

    def render(self):
        self.window_surf.fill(self.background_color)
        self.display.fill((0, 0, 0, 0))

        if self.current_world is not None and self.death_screen.alpha <= 1 and self.too_much_moves.alpha <= 1:
            if self.sea_sound and not self.sea_sound_channel.get_busy():
                self.sea_sound_channel.play(self.sea_sound)
            self.current_world.render()
            for entity in self.current_world.entities:
                entity.render()
            self.player.render()
            self.display.blit(outline(self.display, self.world_outline_color), (0, 0))
            text = (
                f"Moves: {self.current_world.move_count} [/{self.current_world.max_move_count}]\n" f"Health: {self.player.health}"
            )
            move_count_text = self.font.render(text, False, self.text_color)
            move_count_text = outline(move_count_text, self.text_outline)
            self.display.blit(move_count_text, (2, 2))
        elif self.current_world is not None:
            if self.sea_sound: self.sea_sound_channel.fadeout(1000)

        if self.current_world is None:
            self.ending.render()

        self.death_screen.render()
        self.too_much_moves.render()

        self.window_surf.blit(pygame.transform.scale_by(self.display, self.scale), (0, 0))
        pygame.display.flip()

    def update(self):
        if (
            self.current_world is not None
            and tuple(self.player.grid_pos) in self.current_world.grid[0]
            and self.current_world.grid[0][tuple(self.player.grid_pos)][1] == "end"
        ):
            self.dst_display_alpha = 0

            if round(self.display_alpha) <= 1:
                print("nextin")
                self.player.grid_pos.xy = 0, 0
                self.dst_display_alpha = 255
                self.display_alpha = 2
                if self.current_world.move_count <= self.current_world.max_move_count:
                    print("NEXT WORLD!")
                    self.cur_world_id += 1
                else:
                    self.too_much_moves.fade(255)
                if self.current_world is not None:
                    for entity in self.current_world.entities:
                        entity.setup()

        self.display_alpha = pygame.math.lerp(self.display_alpha, self.dst_display_alpha, self.dt * 4)
        self.display.set_alpha(self.display_alpha)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.exit()
            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_LEFT, pygame.K_UP, pygame.K_DOWN, pygame.K_RIGHT):
                    if (
                        not self.player.ready_for_next_move
                        or self.current_world is None
                        or self.player.health <= 0
                        or self.too_much_moves.alpha >= 1
                    ):
                        continue
                    move = {pygame.K_LEFT: (-1, 1), pygame.K_RIGHT: (1, -1), pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1)}
                    if tuple(self.player.grid_pos + move[event.key]) not in self.current_world.grid[0]:
                        continue
                    self.player.ready_for_next_move = False
                    self.player.grid_pos += move[event.key]
                    self.player.last_move = move[event.key]
                    self.current_world.move_count += 1
                    for entity in self.current_world.entities:
                        entity.update()
                elif event.key == pygame.K_r:
                    if self.current_world is None:
                        continue
                    self.death_screen.fade(0)
                    self.too_much_moves.fade(0)
                    self.current_world.move_count = 0
                    self.player.grid_pos.xy = 0, 0
                    self.player.health = self.player.max_health
                    for entity in self.current_world.entities:
                        entity.setup()
        self.player.update()

    def exit(self):
        pygame.quit()
        exit()

    def run(self):
        while True:
            self.render()
            self.update()
            self.dt = self.clock.tick(self.FPS) / 1000
            pygame.display.set_caption(f'{self.title.split("|")[0]}| {self.clock.get_fps()}')

    async def async_run(self):
        while True:
            self.render()
            self.update()
            self.dt = self.clock.tick(self.FPS) / 1000
            pygame.display.set_caption(f'{self.title.split("|")[0]}| {self.clock.get_fps()}')
            await asyncio.sleep(0)


if __name__ == "__main__":
    if "WorldD" in argv:
        WorldD.Main().run()
    else:
        asyncio.run(Main().async_run())
