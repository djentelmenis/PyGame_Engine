import pygame as pg
import sys
from os import path
from random import choice, random
from settings import *
from sprites import Player, Obstacle, Mob, Item
from tilemap import TiledMap, Camera, collide_hit_rect

# HUD functions
def draw_player_health(surf, x, y, pct):
    if pct < 0:
        pct = 0

    # Size
    BAR_LENGTH = 100
    BAR_HEIGHT = 20
    fill = pct * BAR_LENGTH
    outline_rect = pg.Rect(x, y, BAR_LENGTH, BAR_HEIGHT)
    fill_rect = pg.Rect(x, y, fill, BAR_HEIGHT)

    # Color
    if pct > 0.6:
        col = GREEN
    elif pct > 0.3:
        col = YELLOW
    else:
        col = RED

    # Draw
    pg.draw.rect(surf, col, fill_rect)
    pg.draw.rect(surf, WHITE, outline_rect, 2)


class Game:
    def __init__(self):
        # Initializes PyGame buffer=256
        pg.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=256)
        pg.init()

        # Create screen and title
        self.screen = pg.display.set_mode((WIDTH, HEIGHT))
        pg.display.set_caption(TITLE)

        # Clock speed and key delay
        self.clock = pg.time.Clock()
        pg.key.set_repeat(500, 100)

        # Loads data..
        self.load_data()

    def load_data(self):
        # Asset folders
        game_folder = path.dirname(__file__)
        img_folder = path.join(game_folder, 'assets', 'textures')
        snd_folder = path.join(game_folder, 'assets', 'sounds', 'snd')
        music_folder = path.join(game_folder, 'assets', 'sounds', 'music')
        self.map_folder = path.join(game_folder, 'assets', 'maps')

        # Font
        self.title_font = path.join(img_folder, 'ZOMBIE.TTF')
        self.hud_font = path.join(img_folder, 'Impacted2.0.ttf')

        # Object images
        self.dim_screen = pg.Surface(self.screen.get_size()).convert_alpha()
        self.dim_screen.fill((0, 0, 0, 150))
        self.player_img = pg.image.load(path.join(img_folder, 'player', PLAYER_IMG)).convert_alpha()

        self.bullet_images = {}
        self.bullet_images['lg'] = pg.image.load(path.join(img_folder, 'bullet', BULLET_IMG)).convert_alpha()
        self.bullet_images['sm'] = pg.transform.scale(self.bullet_images['lg'], (10, 10))

        self.mob_img = pg.image.load(path.join(img_folder, 'mob', MOB_IMG)).convert_alpha()
        self.splat = pg.image.load(path.join(img_folder, 'mob', SPLAT)).convert_alpha()
        self.splat = pg.transform.scale(self.splat, (64, 64))

        # Particles
        self.gun_flashes = []
        for img in MUZZLE_FLASHES:
            self.gun_flashes.append(pg.image.load(path.join(img_folder, 'particles', img)).convert_alpha())

        # Items
        self.item_images = {}
        for item in ITEM_IMAGES:
            self.item_images[item] = pg.image.load(path.join(img_folder, 'items', ITEM_IMAGES[item])).convert_alpha()

        # Lighting effects
        self.fog = pg.Surface((WIDTH, HEIGHT))
        self.fog.fill(NIGHT_COLOR)
        self.light_mask = pg.image.load(path.join(img_folder, LIGHT_MASK)).convert_alpha()
        self.light_mask = pg.transform.scale(self.light_mask, LIGHT_RADIUS)
        self.light_rect = self.light_mask.get_rect()

        # Sounds
        pg.mixer.music.load(path.join(music_folder, BG_MUSIC))

        self.effects_sounds = {}
        for type in EFFECTS_SOUNDS:
            s = pg.mixer.Sound(path.join(snd_folder, EFFECTS_SOUNDS[type]))
            s.set_volume(0.5)
            self.effects_sounds[type] = s

        self.weapon_sounds = {}
        for weapon in WEAPON_SOUNDS:
            self.weapon_sounds[weapon] = []
            for snd in WEAPON_SOUNDS[weapon]:
                s = pg.mixer.Sound(path.join(snd_folder, snd))
                if weapon == 'shotgun':
                    s.set_volume(0.2)
                else:
                    s.set_volume(0.5)
                self.weapon_sounds[weapon].append(s)

        self.zombie_moan_sounds = []
        for snd in ZOMBIE_MOAN_SOUNDS:
            s = pg.mixer.Sound(path.join(snd_folder, snd))
            s.set_volume(0.2)
            self.zombie_moan_sounds.append(s)

        self.player_hit_sounds = []
        for snd in PLAYER_HIT_SOUNDS:
            self.player_hit_sounds.append(pg.mixer.Sound(path.join(snd_folder, snd)))

        self.zombie_hit_sounds = []
        for snd in ZOMBIE_HIT_SOUNDS:
            s = pg.mixer.Sound(path.join(snd_folder, snd))
            s.set_volume(0.3)
            self.zombie_hit_sounds.append(s)

    def new(self):
        # initialize all variables and do all the setup for a new game
        self.draw_debug = False
        self.paused = False
        self.night = True

        # Sprite groups
        self.all_sprites = pg.sprite.LayeredUpdates()
        self.obstacles = pg.sprite.Group()
        self.mobs = pg.sprite.Group()
        self.bullets = pg.sprite.Group()
        self.items = pg.sprite.Group()

        # Map
        self.map = TiledMap(path.join(self.map_folder, '01.tmx'))
        self.map_img = self.map.make_map()
        self.map_rect = self.map_img.get_rect()

        # Map Objects
        for tile_object in self.map.tmxdata.objects:
            # For spawning in center of tiled object
            obj_center = vec(tile_object.x + tile_object.width / 2,
                             tile_object.y + tile_object.height / 2)
            if tile_object.name == 'player':
                self.player = Player(self, obj_center.x, obj_center.y)
            if tile_object.name == 'zombie':
                Mob(self, obj_center.x, obj_center.y)
            if tile_object.name == 'wall':
                Obstacle(self, tile_object.x, tile_object.y, tile_object.width, tile_object.height)
            if tile_object.name in ['health', 'shotgun']:
                Item(self, obj_center, tile_object.name)

        # Camera object
        self.camera = Camera(self.map.width, self.map.height)

        # Start a new level sound
        self.effects_sounds['level_start'].play()

    def run(self):
        # game loop - set self.playing = False to end the game
        self.playing = True

        # Starts music
        pg.mixer.music.play(loops=-1)

        while self.playing:
            # dt - How much time did the last frame take in ms (For frame-independent movement)
            self.dt = self.clock.tick(FPS) / 1000

            self.events()

            if not self.paused:
                self.update()

            self.draw()

    def events(self):
        # catch all events here
        for event in pg.event.get():
            # Closing window
            if event.type == pg.QUIT:
                self.quit()

            # Keyboard press
            if event.type == pg.KEYDOWN:
                # ESC
                if event.key == pg.K_ESCAPE:
                    self.quit()
                if event.key == pg.K_h:
                    self.draw_debug = not self.draw_debug
                if event.key == pg.K_p:
                    self.paused = not self.paused
                if event.key == pg.K_n:
                    self.night = not self.night

    def update(self):
        # Update portion of the game loop
        self.all_sprites.update()
        self.camera.update(self.player)

        # Game over?
        if len(self.mobs) == 0:
            self.playing = False

        # Player and item
        hits = pg.sprite.spritecollide(self.player, self.items, False)
        for hit in hits:
            if hit.type == 'health' and self.player.health < PLAYER_HEALTH:
                hit.kill()                                  # Destroy item
                self.effects_sounds['health_up'].play()     # Play sound
                self.player.add_health(HEALTH_PACK_AMOUNT)  # Add health
            if hit.type == 'shotgun':
                hit.kill()
                self.effects_sounds['gun_pickup'].play()
                self.player.weapon = 'shotgun'

        # Player and mobs
        hits = pg.sprite.spritecollide(self.player, self.mobs, False, collide_hit_rect)
        for hit in hits:
            # Play sound
            if random() < 0.7:
                choice(self.player_hit_sounds).play()

            # Take damage
            self.player.health -= MOB_DAMAGE
            hit.vel = vec(0, 0)
            if self.player.health <= 0:
                self.playing = False
        if hits:
            self.player.hit()
            self.player.pos += vec(MOB_KNOCKBACK, 0).rotate(-hits[0].rot)

        # Bullets and Mobs
        hits = pg.sprite.groupcollide(self.mobs, self.bullets, False, True)
        for mob in hits:
            for bullet in hits[mob]:
                mob.health -= bullet.damage
            mob.vel = vec(0, 0)

    def draw(self):
        # Shows window title and FPS counter
        pg.display.set_caption("{} FPS - {:.2f}".format(TITLE, self.clock.get_fps()))

        # Fill background
        # self.screen.fill(BGCOLOR)

        # Draws grid
        # self.draw_grid()

        # Draws map
        self.screen.blit(self.map_img, self.camera.apply_rect(self.map_rect))

        # Draws all sprites ant hit rectangles
        for sprite in self.all_sprites:
            if isinstance(sprite, Mob):
                sprite.draw_health()
            self.screen.blit(sprite.image, self.camera.apply(sprite))
            if self.draw_debug:
                pg.draw.rect(self.screen, CYAN, self.camera.apply_rect(sprite.hit_rect), 1)
        if self.draw_debug:
            for obstacle in self.obstacles:
                pg.draw.rect(self.screen, CYAN, self.camera.apply_rect(obstacle.rect), 1)

        # Lighting effects
        if self.night:
            self.render_fog()

        # Draws HUD
        draw_player_health(self.screen, 10, 10, self.player.health / PLAYER_HEALTH)
        self.draw_text('Zombies: {}'.format(len(self.mobs)), self.hud_font, 30, WHITE, WIDTH - 10, 10 , align="ne")

        # Draws PAUSED
        if self.paused:
            self.screen.blit(self.dim_screen, (0, 0))
            self.draw_text("Paused", self.title_font, 105, RED, WIDTH / 2, HEIGHT / 2, align="center")

        # Flips/Updates screen
        pg.display.flip()

    def render_fog(self):
        self.fog.fill(NIGHT_COLOR)
        self.light_rect.center = self.camera.apply(self.player).center
        self.fog.blit(self.light_mask, self.light_rect)
        self.screen.blit(self.fog, (0, 0), special_flags=pg.BLEND_MULT)

    def draw_text(self, text, font_name, size, color, x, y, align="nw"):
        font = pg.font.Font(font_name, size)
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect()
        if align == "nw":
            text_rect.topleft = (x, y)
        if align == "ne":
            text_rect.topright = (x, y)
        if align == "sw":
            text_rect.bottomleft = (x, y)
        if align == "se":
            text_rect.bottomright = (x, y)
        if align == "n":
            text_rect.midtop = (x, y)
        if align == "s":
            text_rect.midbottom = (x, y)
        if align == "e":
            text_rect.midright = (x, y)
        if align == "w":
            text_rect.midleft = (x, y)
        if align == "center":
            text_rect.center = (x, y)
        self.screen.blit(text_surface, text_rect)

    def draw_grid(self):
        for x in range(0, WIDTH, TILESIZE):
            pg.draw.line(self.screen, LIGHTGREY, (x, 0), (x, HEIGHT))
        for y in range(0, HEIGHT, TILESIZE):
            pg.draw.line(self.screen, LIGHTGREY, (0, y), (WIDTH, y))

    def show_start_screen(self):
        pass

    def show_go_screen(self):
        self.screen.fill(BLACK)
        self.draw_text("GAME OVER", self.title_font, 100, RED, WIDTH / 2, HEIGHT / 2, align="center")
        self.draw_text("Press a key to start", self.title_font, 75, WHITE, WIDTH / 2, HEIGHT * 3 / 4, align="center")
        pg.display.flip()
        self.wait_for_key()

    def wait_for_key(self):
        pg.event.wait()
        waiting = True
        while waiting:
            self.clock.tick(FPS)
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    waiting = False
                    self.quit()
                if event.type == pg.KEYUP:
                    waiting = False

    def quit(self):
        pg.quit()
        sys.exit()


# create the game object
g = Game()
g.show_start_screen()
while True:
    g.new()
    g.run()
    g.show_go_screen()
