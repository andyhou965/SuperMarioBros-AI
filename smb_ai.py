import retro
from PyQt5 import QtGui, QtWidgets
from PyQt5.QtGui import QPainter, QBrush, QPen, QPolygonF, QColor, QImage, QPixmap
from PyQt5.QtCore import Qt, QPointF, QTimer, QRect
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel
from PIL import Image
from PIL.ImageQt import ImageQt
from typing import Tuple, List
import random
import sys
import math
import numpy as np
from utils import SMB, EnemyType, StaticTileType, ColorMap, DynamicTileType
from config import Config
from nn_viz import NeuralNetworkViz
from mario import Mario

from genetic_algorithm.individual import Individual
from genetic_algorithm.population import Population
from genetic_algorithm.selection import elitism_selection, tournament_selection, roulette_wheel_selection
from genetic_algorithm.crossover import simulated_binary_crossover as SBX
from genetic_algorithm.mutation import gaussian_mutation

normal_font = QtGui.QFont('Times', 11, QtGui.QFont.Normal)
font_bold = QtGui.QFont('Times', 11, QtGui.QFont.Bold)


def draw_border(painter: QPainter, size: Tuple[float, float]) -> None:
    painter.setPen(QPen(Qt.black, 1, Qt.SolidLine))
    painter.setBrush(QBrush(Qt.green, Qt.NoBrush))
    painter.setRenderHint(QPainter.Antialiasing)
    points = [(0, 0), (size[0], 0), (size[0], size[1]), (0, size[1])]
    qpoints = [QPointF(point[0], point[1]) for point in points]
    polygon = QPolygonF(qpoints)
    painter.drawPolygon(polygon)


class Visualizer(QtWidgets.QWidget):
    def __init__(self, parent, size, config: Config, nn_viz: NeuralNetworkViz):
        super().__init__(parent)
        self.size = size
        self.config = config
        self.nn_viz = nn_viz
        self.ram = None
        self.x_offset = 150
        self.tile_width, self.tile_height = self.config.Graphics.tile_size
        self.tiles = None
        self.enemies = None

    def _draw_region_of_interest(self, painter: QPainter) -> None:
        # Grab mario row/col in our tiles
        mario = SMB.get_mario_location_on_screen(self.ram)
        mario_row, mario_col = SMB.get_tile_loc(mario.x, mario.y)
        mario_row, mario_col = SMB.get_mario_row_col(self.ram)
        # Determine how many tiles up, down, left, right we need
        up, down, left, right = self.config.NeuralNetwork.inputs_size
        min_row = max(0, mario_row - up)
        max_row = min(14, mario_row + down)
        min_col = max(0, mario_col - left)
        max_col = min(15, mario_col + right)
        
        x, y = min_col, min_row
        width = max_col - min_col + 1
        height = max_row - min_row + 1

        color = QColor(255, 0, 217)
        painter.setPen(QPen(color, 3.0, Qt.SolidLine))
        painter.setBrush(QBrush(Qt.NoBrush))
        painter.drawRect(x*self.tile_width + 5 + self.x_offset, y*self.tile_height + 5, width*self.tile_width, height*self.tile_height)


    def draw_tiles(self, painter: QPainter):
        if not self.tiles:
            return
        # tiles = self.get_tiles()
        # tiles = SMB.get_tiles(self.ram)
        # enemies = SMB.get_enemy_locations(self.ram)
        # mario_row, mario_col = SMB.get_mario_row_col(self.ram)
        # tiles[(mario_row, mario_col)] = DynamicTileType(0xAA)
        # print(self.ram[0x500:0x69f+1])
        # print(SMB.get_tiles(self.ram))
        # SMB.get_tiles(self.ram)
        # print(SMB.get_tiles(self.ram))
        # mario = SMB.get_mario_location_in_level(self.ram)
        # x, y = mario.x, mario.y 
        # page = (x // 256) % 2
        # sub_page_x = (x % 256) // 16
        # sub_page_y = (y - 32) // 16 
        # mario_screen = SMB.get_mario_location_on_screen(self.ram)
        # tiles_left = mario_screen.x // 16
        # tiles_up = mario_screen.y // 16
        # print('page: {}, subx: {}, suby: {}'.format(page, sub_page_x, sub_page_y))
        # print('left: {}, above: {}'.format(tiles_left, tiles_up))
        # assert tiles.shape == (13,16)
        for row in range(15):
            for col in range(16):
                painter.setPen(QPen(Qt.black,  1, Qt.SolidLine))
                painter.setBrush(QBrush(Qt.white, Qt.SolidPattern))
                x_start = 5 + (self.tile_width * col) + self.x_offset
                y_start = 5 + (self.tile_height * row)

                loc = (row, col)
                tile = self.tiles[loc]

                if isinstance(tile, (StaticTileType, DynamicTileType, EnemyType)):
                    rgb = ColorMap[tile.name].value
                    color = QColor(*rgb)
                    painter.setBrush(QBrush(color))
                else:
                    pass

                painter.drawRect(x_start, y_start, self.tile_width, self.tile_height)

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)
        draw_border(painter, self.size)
        if not self.ram is None:
            self.draw_tiles(painter)
            self._draw_region_of_interest(painter)
            self.nn_viz.show_network(painter)

        painter.end()

    def _update(self):
        self.update()
    
    

class GameWindow(QtWidgets.QWidget):
    def __init__(self, parent, size, config: Config):
        super().__init__(parent)
        self.size = size
        self.config = config
        self.screen = None
        self.img_label = QtWidgets.QLabel(self)
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addWidget(self.img_label)
        self.setLayout(self.layout)

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)
        draw_border(painter, self.size)
        if not self.screen is None:
            # self.img_label = QtWidgets.QLabel(self.centralWidget)
            # screen = self.env.reset()
  
            width = self.screen.shape[0] * 3 
            height = int(self.screen.shape[1] * 2)
            # resized = original.resize((width, height))
            resized = self.screen
            original = QImage(self.screen, self.screen.shape[1], self.screen.shape[0], QImage.Format_RGB888)
            # Create the image and label
            # image = ImageQt(resized)
            qimage = QImage(original)
            # Center where the image will go
            x = (self.screen.shape[0] - width) // 2
            y = (self.screen.shape[1] - height) // 2
            self.img_label.setGeometry(0, 0, width, height)
            # Add image
            pixmap = QPixmap(qimage)
            pixmap = pixmap.scaled(width, height, Qt.KeepAspectRatio)
            # print(pixmap.width(), pixmap.height())
            self.img_label.setPixmap(pixmap)
        # print('here')
            
        painter.end()

    def _update(self):
        self.update()

class InformationWidget(QtWidgets.QWidget):
    def __init__(self, parent, size, config):
        super().__init__(parent)
        self.size = size
        self.config = config

        self.grid = QtWidgets.QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self._init_window()
        self.setLayout(self.grid)

    def _init_window(self) -> None:
        info_vbox = QVBoxLayout()
        info_vbox.setContentsMargins(0, 0, 0, 0)

        # Current Generation
        generation_label = QLabel()
        generation_label.setFont(font_bold)
        generation_label.setText('Generation:')
        generation_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.generation = QLabel()
        self.generation.setFont(normal_font)
        self.generation.setText("<font color='red'>" + '1' + '</font>')
        self.generation.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hbox_generation = QHBoxLayout()
        hbox_generation.setContentsMargins(5, 0, 0, 0)
        hbox_generation.addWidget(generation_label, 1)
        hbox_generation.addWidget(self.generation, 1)
        info_vbox.addLayout(hbox_generation)

        # Current individual
        current_individual_label = QLabel()
        current_individual_label.setFont(font_bold)
        current_individual_label.setText('Individual:')
        current_individual_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.current_individual = QLabel()
        self.current_individual.setFont(normal_font)
        self.current_individual.setText('1/{}'.format(self.config.Selection.num_parents))
        self.current_individual.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hbox_current_individual = QHBoxLayout()
        hbox_current_individual.setContentsMargins(5, 0, 0, 0)
        hbox_current_individual.addWidget(current_individual_label, 1)
        hbox_current_individual.addWidget(self.current_individual, 1)
        info_vbox.addLayout(hbox_current_individual)

        # Best fitness
        best_fitness_label = QLabel()
        best_fitness_label.setFont(font_bold)
        best_fitness_label.setText('Best Fitness:')
        best_fitness_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.best_fitness = QLabel()
        self.best_fitness.setFont(normal_font)
        self.best_fitness.setText('0')
        self.best_fitness.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hbox_best_fitness = QHBoxLayout()
        hbox_best_fitness.setContentsMargins(5, 0, 0, 0)
        hbox_best_fitness.addWidget(best_fitness_label, 1)
        hbox_best_fitness.addWidget(self.best_fitness, 1)
        info_vbox.addLayout(hbox_best_fitness) 

        # Max Distance
        max_distance_label = QLabel()
        max_distance_label.setFont(font_bold)
        max_distance_label.setText('Max Distance:')
        max_distance_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.max_distance = QLabel()
        self.max_distance.setFont(normal_font)
        self.max_distance.setText('0')
        self.max_distance.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hbox_max_distance = QHBoxLayout()
        hbox_max_distance.setContentsMargins(5, 0, 0, 0)
        hbox_max_distance.addWidget(max_distance_label, 1)
        hbox_max_distance.addWidget(self.max_distance, 1)
        info_vbox.addLayout(hbox_max_distance)  

        self.grid.addLayout(info_vbox, 0, 0)




class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.top = 150
        self.left = 150
        self.width = 1100
        self.height = 700

        self.title = 'Super Mario Bros AI'
        self.env = retro.make(game='SuperMarioBros-Nes', state='Level2-1')

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update)
        # Keys correspond with B, NULL, SELECT, START, U, D, L, R, A
        # index                0  1     2       3      4  5  6  7  8
        self.keys = np.array( [0, 0,    0,      0,     0, 0, 0, 0, 0], np.int8)
        self.i = 1
        # I only allow U, D, L, R, A, B and those are the indices in which the output will be generated
        # We need a mapping from the output to the keys above
        self.ouput_to_keys_map = {
            0: 4,  # U
            1: 5,  # D
            2: 6,  # L
            3: 7,  # R
            4: 8,  # A
            5: 0   # B
        }

        # Initialize the starting population
        individuals: List[Individual] = []
        for _ in range(self.config.Selection.num_parents):
            individual = Mario(self.config)
            individuals.append(individual)

        self.best_fitness = 0.0
        self._current_individual = 0
        self.population = Population(individuals)

        self.mario = self.population.individuals[self._current_individual]
        self.current_generation = 0
        self.max_distance = 0  # Track farthest traveled in level
        self.max_fitness = 0.0

        # Determine the size of the next generation based off selection type
        self._next_gen_size = None
        if self.config.Selection.selection_type == 'plus':
            self._next_gen_size = self.config.Selection.num_parents + self.config.Selection.num_offspring
        elif self.config.Selection.selection_type == 'comma':
            self._next_gen_size = self.config.Selection.num_offspring

        self.init_window()
        self.show()

        self._timer.start(1000 // 60)

    def init_window(self) -> None:
        self.centralWidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.centralWidget)
        self.setWindowTitle(self.title)
        self.setGeometry(self.top, self.left, self.width, self.height)

        self.game_window = GameWindow(self.centralWidget, (514, 480), self.config)
        self.game_window.setGeometry(QRect(1100-514, 0, 514, 480))
        self.game_window.setObjectName('game_window')
        # # Reset environment and pass the screen to the GameWindow
        screen = self.env.reset()
        self.game_window.screen = screen
        # self.game_window.update()


        self.viz = NeuralNetworkViz(self.centralWidget, self.mario, (1100-514, 700), self.config)

        self.viz_window = Visualizer(self.centralWidget, (1100-514, 700), self.config, self.viz)
        self.viz_window.setGeometry(0, 0, 1100-514, 700)
        self.viz_window.setObjectName('viz_window')
        self.viz_window.ram = self.env.get_ram()
        
        # self.width = 1100
        # self.height = 700
        self.info_window = InformationWidget(self.centralWidget, (514, 700-480), self.config)
        self.info_window.setGeometry(QRect(1100-514, 480, 514, 700-480))

    def keyPressEvent(self, event):
        k = event.key()
        m = {
            Qt.Key_Right : 7,
            Qt.Key_C : 8,
            Qt.Key_X: 0,
            Qt.Key_Left: 6,
            Qt.Key_Down: 5
        }
        if k in m:
            self.keys[m[k]] = 1
        if k == Qt.Key_D:
            tiles = SMB.get_tiles(self.env.get_ram(), False)
            print(SMB.get_mario_location_in_level(self.env.get_ram()))
            # for row in range(15):
            #     for col in range(16):
            #         loc = (row, col)
            #         print('{:02X}'.format(tiles[loc].value), end=' ')
            #     print()

    def keyReleaseEvent(self, event):
        k = event.key()
        m = {
            Qt.Key_Right : 7,
            Qt.Key_C : 8,
            Qt.Key_X: 0,
            Qt.Key_Left: 6,
            Qt.Key_Down: 5
        }
        if k in m:
            self.keys[m[k]] = 0

        
    def next_generation(self) -> None:
        self._increment_generation()
        self._current_individual = 0
        self.info_window.current_individual.setText('{}/{}'.format(self._current_individual + 1, self._next_gen_size))

        # Calculate fitness
        for individual in self.population.individuals:
            individual.calculate_fitness()

        self.population.individuals = elitism_selection(self.population, self.config.Selection.num_parents)

        random.shuffle(self.population.individuals)
        next_pop = []

        # Parents + offspring
        if self.config.Selection.selection_type == 'plus':
            # Decrement lifespan
            for individual in self.population.individuals:
                individual.lifespan -= 1

            for individual in self.population.individuals:
                config = individual.config
                chromosome = individual.network.params
                hidden_layer_architecture = individual.hidden_layer_architecture
                hidden_activation = individual.hidden_activation
                output_activation = individual.output_activation
                lifespan = individual.lifespan

                # If the indivdual would be alve, add it to the next pop
                if lifespan > 0:
                    m = Mario(config, chromosome, hidden_layer_architecture, hidden_activation, output_activation, lifespan)
                    next_pop.append(m)

        while len(next_pop) < self._next_gen_size:
            selection = self.config.Crossover.crossover_selection
            if selection == 'tournament':
                p1, p2 = tournament_selection(self.population, 2, self.config.Crossover.tournament_size)
            elif selection == 'roulette':
                p1, p2 = roulette_wheel_selection(self.population, 2)
            else:
                raise Exception('crossover_selection "{}" is not supported'.format(selection))

            L = len(p1.network.layer_nodes)
            c1_params = {}
            c2_params = {}

            # Each W_l and b_l are treated as their own chromosome.
            # Because of this I need to perform crossover/mutation on each chromosome between parents
            for l in range(1, L):
                p1_W_l = p1.network.params['W' + str(l)]
                p2_W_l = p2.network.params['W' + str(l)]  
                p1_b_l = p1.network.params['b' + str(l)]
                p2_b_l = p2.network.params['b' + str(l)]

                # Crossover
                # @NOTE: I am choosing to perform the same type of crossover on the weights and the bias.
                c1_W_l, c2_W_l, c1_b_l, c2_b_l = self._crossover(p1_W_l, p2_W_l, p1_b_l, p2_b_l)

                # Mutation
                # @NOTE: I am choosing to perform the same type of mutation on the weights and the bias.
                self._mutation(c1_W_l, c2_W_l, c1_b_l, c2_b_l)

                # Assign children from crossover/mutation
                c1_params['W' + str(l)] = c1_W_l
                c2_params['W' + str(l)] = c2_W_l
                c1_params['b' + str(l)] = c1_b_l
                c2_params['b' + str(l)] = c2_b_l

                #  Clip to [-1, 1]
                np.clip(c1_params['W' + str(l)], -1, 1, out=c1_params['W' + str(l)])
                np.clip(c2_params['W' + str(l)], -1, 1, out=c2_params['W' + str(l)])
                np.clip(c1_params['b' + str(l)], -1, 1, out=c1_params['b' + str(l)])
                np.clip(c2_params['b' + str(l)], -1, 1, out=c2_params['b' + str(l)])


            c1 = Mario(self.config, c1_params, p1.hidden_layer_architecture, p1.hidden_activation, p1.output_activation, p1.lifespan)
            c2 = Mario(self.config, c2_params, p2.hidden_layer_architecture, p2.hidden_activation, p2.output_activation, p2.lifespan)

            next_pop.extend([c1, c2])

        # Set next generation
        random.shuffle(next_pop)
        self.population.individuals = next_pop

    def _crossover(self, parent1_weights: np.ndarray, parent2_weights: np.ndarray,
                   parent1_bias: np.ndarray, parent2_bias: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        eta = self.config.Crossover.sbx_eta

        # SBX weights and bias
        child1_weights, child2_weights = SBX(parent1_weights, parent2_weights, eta)
        child1_bias, child2_bias =  SBX(parent1_bias, parent2_bias, eta)

        return child1_weights, child2_weights, child1_bias, child2_bias

    def _mutation(self, child1_weights: np.ndarray, child2_weights: np.ndarray,
                  child1_bias: np.ndarray, child2_bias: np.ndarray) -> None:
        mutation_rate = self.config.Mutation.mutation_rate
        scale = self.config.Mutation.gaussian_mutation_scale

        if self.config.Mutation.mutation_rate_type == 'dynamic':
            mutation_rate = mutation_rate / math.sqrt(self.current_generation + 1)
        
        # Mutate weights
        gaussian_mutation(child1_weights, mutation_rate, scale=scale)
        gaussian_mutation(child2_weights, mutation_rate, scale=scale)

        # Mutate bias
        gaussian_mutation(child1_bias, mutation_rate, scale=scale)
        gaussian_mutation(child2_bias, mutation_rate, scale=scale)

    def _increment_generation(self) -> None:
        self.current_generation += 1
        txt = "<font color='red'>" + str(self.current_generation + 1) + '</font>'
        self.info_window.generation.setText(txt)


    def _update(self) -> None:
        """
        This is the main update method which is called based on the FPS timer.
        Genetic Algorithm updates, window updates, etc. are performed here.
        """
        self.i += 1
        # right =   np.array([0,0,0,0,0,0,0,1,0], np.int8)
        # nothing = np.array([0,0,0,0,0,0,0,0,0], np.int8)
        # ret = self.env.step(self.keys)
        ret = self.env.step(self.mario.buttons_to_press)
        self.game_window.screen = ret[0]
        # self.viz_window.ram = self.env.get_ram()
        
        self.game_window._update()

        if self.i % 5 != 0:
            return

        ram = self.env.get_ram()
        tiles = SMB.get_tiles(ram)  # Grab tiles on the screen
        enemies = SMB.get_enemy_locations(ram)

        # self.mario.set_input_as_array(ram, tiles)
        self.mario.update(ram, tiles, self.keys, self.ouput_to_keys_map)
        

        self.viz_window.ram = ram
        self.viz_window.tiles = tiles
        self.viz_window.enemies = enemies
        self.viz_window._update()


    
        if self.mario.is_alive:
            # New farthest distance?
            if self.mario.farthest_x > self.max_distance:
                self.max_distance = self.mario.farthest_x
                self.info_window.max_distance.setText(str(self.max_distance))
        else:
            self.mario.calculate_fitness()
            fitness = self.mario.fitness
            
            if fitness > self.max_fitness:
                self.max_fitness = fitness
                max_fitness = '{:.2f}'.format(self.max_fitness)
                self.info_window.best_fitness.setText(max_fitness)


            self._current_individual += 1

            # Is it the next generation?
            if (self.current_generation > 0 and self._current_individual == self._next_gen_size) or\
                (self.current_generation == 0 and self._current_individual == self.config.Selection.num_parents):
                self.next_generation()
            else:
                if self.current_generation == 0:
                    current_pop = self.config.Selection.num_parents
                else:
                    current_pop = self._next_gen_size
                self.info_window.current_individual.setText('{}/{}'.format(self._current_individual + 1, current_pop))
            

            self.game_window.screen = self.env.reset()
            self.mario = self.population.individuals[self._current_individual]
            self.viz.mario = self.mario
        



if __name__ == "__main__":
    config = Config('settings.config')
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(config)
    sys.exit(app.exec_())