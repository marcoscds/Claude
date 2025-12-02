import os
import threading
import numpy as np # type: ignore
import matplotlib.pyplot as plt # type: ignore

from kivy.app import App
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.utils import platform
from kivy.core.window import Window 
from kivy.properties import NumericProperty, StringProperty, ObjectProperty

# -------------------------------------------------------------------------------------------------------------
#                                          PERMISSÕES ANDROID PARA BLUETOOTH
# -------------------------------------------------------------------------------------------------------------
if platform == 'android':
    try:
        from android.permissions import request_permissions, Permission # type: ignore

        def pedir_permissoes_bluetooth():
            try:   
                request_permissions([
                    Permission.BLUETOOTH_CONNECT, # BLUETOOTH_CONNECT é essencial para pareados
                    Permission.BLUETOOTH_ADMIN,
                    Permission.BLUETOOTH_SCAN,
                    Permission.ACCESS_COARSE_LOCATION,
                    Permission.ACCESS_FINE_LOCATION,
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE
                ])
            except Exception as e:
                message = "Erro ao pedir permissões: {e}"
                popup = ConfirmationPopup(message=message)
                popup.open()

    except ImportError:
        pass
else:
    # Define uma função dummy para plataformas não-Android (Desktop)
    def pedir_permissoes_bluetooth():
        pass

# === Importações Bluetooth (ANDROID) ===
try:
    from jnius import autoclass # type: ignore
    BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
    BluetoothDevice = autoclass('android.bluetooth.BluetoothDevice')
    BluetoothSocket = autoclass('android.bluetooth.BluetoothSocket')
    UUID = autoclass('java.util.UUID')
except ImportError:
    BluetoothAdapter = None
    BluetoothDevice = None
    BluetoothSocket = None
    UUID = None

# -------------------------------------------------------------------------------------------------------------
#                                                   VARIÁVEIS
# -------------------------------------------------------------------------------------------------------------

angles_deg = []
powers = []
reference_power = None
BLUETOOTH_STATUS = StringProperty("Status: Desconectado.")
BLUETOOTH_DEVICE_NAME = "ESP32MotorControl" 
BLUETOOTH_UUID = "00001101-0000-1000-8000-00805F9B34FB" # UUID padrão SPP (Serial Port Profile)
bluetooth_socket = None 

# Carregamento do KV 
if os.path.exists('main.kv'):Builder.load_file('main.kv')

# -------------------------------------------------------------------------------------------------------------
#                                                   CLASSES DE TELA
# -------------------------------------------------------------------------------------------------------------
class BluetoothScreen(Screen):
    bluetooth_status = StringProperty("Status: Desconectado.") 
    
    def connect_bluetooth(self):
        """Busca o dispositivo pareado e tenta conectar."""
        
        # Checa a plataforma e as dependências
        if platform != 'android' or BluetoothAdapter is None:
            message = "Bluetooth só funciona no Android."
            self.show_popup_message(message)
            return
        adapter = BluetoothAdapter.getDefaultAdapter()
        if not adapter or not adapter.isEnabled():
            message = "Bluetooth Desabilitado. Habilite nas Configurações."
            self.show_popup_message(message)
            return

        self.bluetooth_status = "Status: Buscando Dispositivo..."
        target_device = None
        
        # Percorre a lista de dispositivos pareados
        for device in adapter.getBondedDevices().toArray():
            if device.getName() == BLUETOOTH_DEVICE_NAME:
                target_device = device
                break

        if target_device is None:
            message = f"Dispositivo '{BLUETOOTH_DEVICE_NAME}' não encontrado na lista de pareados."
            self.bluetooth_status = "Status: Dispositivo Não Encontrado."
            self.show_popup_message(message)
            return
        
        self.bluetooth_status = f"Status: Conectando a {BLUETOOTH_DEVICE_NAME}..."

        # Tenta conectar em uma nova thread
        connect_thread = threading.Thread(target=self._attempt_connection, args=(target_device,), daemon=True)
        connect_thread.start()


    def _attempt_connection(self, target_device):
        """Função que executa a tentativa de conexão (em uma thread separada)."""
        global bluetooth_socket
        uuid_obj = UUID.fromString(BLUETOOTH_UUID) # Cria o UUID
        
        # Tenta criar o socket RFCOMM (Bluetooth Clássico)
        try:
            bluetooth_socket = target_device.createRfcommSocketToServiceRecord(uuid_obj)
        except Exception as e:
            message = f"ERRO ao criar socket: {e}"
            Clock.schedule_once(lambda dt: self.show_popup_message(message), 0)
            Clock.schedule_once(lambda dt: setattr(self, 'bluetooth_status', "Status: Erro de Socket."), 0)
            return

        # Tenta conectar o socket
        try:
            message = "Iniciando Conexão..."
            self.show_popup_message(message)
            bluetooth_socket.connect() # ESTE É O BLOQUEANTE
            
            # Conexão bem-sucedida
            Clock.schedule_once(lambda dt: setattr(self, 'bluetooth_status', "Status: CONECTADO!"), 0)
            Clock.schedule_once(lambda dt: self.show_popup_message("Conexão Bluetooth Estabelecida com Sucesso!"), 0)
            
            # Ativa o botão de avançar (deve ser agendado para rodar na thread principal)
            Clock.schedule_once(lambda dt: setattr(self.manager.get_screen('motor_control').ids.control_button, 'disabled', False), 0)

            # INICIA A THREAD DE LEITURA (NOVA THREAD PARA RECEBIMENTO DE DADOS)
            read_thread = threading.Thread(target=self.read_bluetooth_data, daemon=True)
            read_thread.start()

        except Exception as e:
            # Erro de conexão (dispositivo não está pronto, fora do alcance, etc.)
            message = f"ERRO de Conexão. Tente Novamente ou \nPareie o Dispositivo: {e}"
            Clock.schedule_once(lambda dt: self.show_popup_message(message), 0)
            Clock.schedule_once(lambda dt: setattr(self, 'bluetooth_status', "Status: Falha na Conexão."), 0)
            try:
                bluetooth_socket.close()
            except:
                pass
            bluetooth_socket = None

        except Exception as e:
            Clock.schedule_once(lambda dt: setattr(self, 'bluetooth_status', "Status: Conexão Perdida."), 0)
            bluetooth_socket = None


    # MÉTODOS DE MUDANÇA DE TELA 
    def go_to_motor_control(self):
        """Muda para a tela de controle do motor."""
        if bluetooth_socket is not None or platform != 'android':
            self.manager.current = 'motor_control'
        else:
            self.manager.current = 'motor_control'
            self.show_popup_message("Conecte-se ao Bluetooth \n Antes de Avançar")


    def show_popup_message(self, message):
        """Exibe o popup de confirmação."""
        popup = ConfirmationPopup(message=message)
        popup.open()

class MotorControlScreen(Screen):
    posicao = NumericProperty(0)
    passo = NumericProperty(1) 
    pos_text = StringProperty("0°")
    last_slider_value = NumericProperty(0) # Último valor enviado pelo slider (para cálculo de diferença)

    def __init__(self, **kwargs):  # Inicializa o last_slider_value com a posição inicial
        super().__init__(**kwargs)
        self.last_slider_value = int(self.posicao) 
        self.atualizar_label()

    def atualizar_label(self, *args):
        self.pos_text = f"{int(self.posicao)}°"
        
    # Método para troca de Strings com Bluetooth

    def _format_command(self, direction, step_value):
        """Formata o comando conforme padrão programado na ESP"""
        # Garante que o passo seja um inteiro e formata com zeros à esquerda (03d)
        step_value = max(0, min(999, int(step_value))) # Limita o passo entre 0 e 999
        formatted_step = f"{step_value:03d}"
        command = f"&{direction}{formatted_step}"
        return command

    def send_bluetooth_data(self, data):
        """Envia dados via Bluetooth se o socket estiver ativo, ou simula no console."""
        global bluetooth_socket
        if bluetooth_socket is not None:
            try: # Envia os dados como bytes
                output_stream = bluetooth_socket.getOutputStream()
                output_stream.write(data.encode('utf-8'))
                output_stream.flush()
            except Exception as e:
                self.manager.get_screen('bluetooth_connection').show_popup_message(f"ERRO DE ENVIO BT: {e}")
            except AttributeError:
                pass
        else:
            print(f"Comando simulado: {data}")

    def send_step_command(self, direction):
        """ Envia o passo definido na direção especificada, respeitando os limites de 0° e 360°. """
        current_pos = self.posicao 
        step = self.passo          
        
        if direction == 'R':
            new_pos = min(360, current_pos + step)
        else:
            new_pos = max(0, current_pos - step)
            
        actual_step = abs(int(new_pos) - int(current_pos)) # Calcula o passo REAL que o motor deve dar
        if actual_step == 0: 
            return 

        command = self._format_command(direction, actual_step) 
        self.send_bluetooth_data(command)
        
        # Atualiza a posição
        self.posicao = new_pos
        self.atualizar_label()
        self.last_slider_value = int(self.posicao) # Atualiza o last_slider_value


   # Botão 'Registrar Potencia'
    def register_power_command(self, potencia_input_ref, potencia_inserida_str):
        """ Envia o passo definido para a direita, se o limite de 360° não for excedido."""
        try:
            float(potencia_inserida_str)
            valor_valido = True
        except ValueError:
            valor_valido = False
        
        if valor_valido:
            current_pos = self.posicao 
            step = self.passo          
            
            new_pos = min(360, current_pos + step) 
            actual_step = abs(int(new_pos) - int(current_pos)) 

            if actual_step == 0:
                message = f"Valor Máximo Atingido (360°)"
                popup = ConfirmationPopup(message=message)
                popup.open()
                return
            
            command = self._format_command('R', actual_step)
            self.send_bluetooth_data(command)
            
            self.adicionar_medida_do_app(potencia_input_ref, self.posicao, potencia_inserida_str)
            
            self.posicao = new_pos
            self.atualizar_label()
            self.last_slider_value = int(self.posicao)
            
            potencia_input_ref.text = '' # Limpa o campo
            Clock.schedule_once(lambda dt: self.set_focus_on_input(potencia_input_ref), 0.05) # Mantém o foco
            
        else:
            message = f"Insira um Valor de Potência"
            popup = ConfirmationPopup(message=message)
            popup.open()

    # Trata a Mudança de Posição no Slider
    def on_slider_touch_up(self):
        """Calcula a diferença de posição do slider e envia o comando '&R/L<diff>'. """
        
        new_value = int(self.posicao) 
        diff = abs(new_value - self.last_slider_value) # Calcula a diferença absoluta (o passo a ser enviado)
        
        if diff == 0:
            return

        if new_value > self.last_slider_value: 
            direction = 'R'
        else:
            direction = 'L'
        # Formata, envia o comando e atualiza
        command = self._format_command(direction, diff)
        self.send_bluetooth_data(command)
        self.last_slider_value = new_value
        
    # -------------------- Funções de Movimento -------------------------------
    def aumentar(self):
        self.posicao = min(360, self.posicao + self.passo)
        self.atualizar_label()

    def diminuir(self):
        self.posicao = max(0, self.posicao - self.passo)
        self.atualizar_label()

    def slider_moved(self, widget):
        self.posicao = int(widget.value)
        self.atualizar_label()

    def definir_passo(self, valor):
        new_passo = int(valor)
        self.passo = new_passo
            
    # ---------------- Funções de Plotagem do Gráfico ---------------------------------
    def adicionar_medida_do_app(self, potencia_input_ref, posicao_em_graus, potencia_inserida_str):
        try:
            potencia = float(potencia_inserida_str) #Tenta converter a string para float
        except ValueError:
            Clock.schedule_once(lambda dt: potencia_input_ref.focus == True, 0.05)
            return

        angulo = int(posicao_em_graus)
        
        # Adiciona ou Atualiza a medida
        if angulo not in angles_deg:
            angles_deg.append(angulo)
            powers.append(potencia)
        else:
            index = angles_deg.index(angulo)
            powers[index] = potencia
            message = f" Medida atualizada:\nÂngulo {angulo}°\nPotência {potencia} dBm"
            popup = ConfirmationPopup(message=message)
            popup.open()
        
        # Adiciona Passo
        self.posicao = min(360, self.posicao + self.passo)
        self.atualizar_label()
        self.last_slider_value = int(self.posicao)
        potencia_input_ref.text = '' # Limpa o campo
        Clock.schedule_once(lambda dt: self.set_focus_on_input(potencia_input_ref), 0.05) # Mantém o foco
    
    # Função auxiliar para redefinir o foco
    def set_focus_on_input(self, input_widget):
        """Função auxiliar para redefinir o foco de forma robusta."""
        input_widget.focus = True

    
    # ------------------------ NOVA LÓGICA DE PLOTAGEM CENTRALIZADA ---------------------------
    def _create_polar_plot(self, graph_title, freq_text, custom_scales, temp_path=None):
        """Função auxiliar para criar o plot polar (usado por Save e Preview).
           Se temp_path for fornecido, a figura é salva para preview.
           Retorna a figura (plt.gcf())
        """
        global reference_power 
        
        # O cálculo do Ganho Normalizado e o fechamento do loop são os mesmos
        reference_power = np.max(powers) 
        angles_np = np.array(angles_deg) 
        powers_np = np.array(powers)
        angles_rad = np.deg2rad(angles_np)
        gains_dB = powers_np - reference_power
        sorted_indices = np.argsort(angles_rad)
        angles_rad = angles_rad[sorted_indices]
        gains_dB = gains_dB[sorted_indices]
        angles_rad = np.append(angles_rad, angles_rad[0])
        gains_dB = np.append(gains_dB, gains_dB[0])
        
        # -------------------------------------------------------------------------
        # Lógica de Definição das Escalas Radiais
        # -------------------------------------------------------------------------
        
        # 1. Define o limite máximo (0 dB de ganho)
        max_gain = 0 
        
        if custom_scales:
            # Opção Personalizada: Usa as escalas fornecidas pelo usuário
            
            # Filtra e adiciona 0 dB se necessário (para garantir que a borda externa seja 0dB)
            if 0 not in custom_scales:
                custom_scales.append(0.0)
            
            # Remove duplicatas e ordena da menor (mais negativa) para a maior (0)
            radial_ticks = np.array(sorted(list(set(custom_scales))))
            
            # O limite mínimo (mais interno) do gráfico será a menor escala fornecida
            min_gain = np.min(radial_ticks) 

        else:
            # Opção Automática (Padrão): Lógica original
            min_data_gain = np.floor(np.min(gains_dB) / 5) * 5 # Mínimo automático, arredondado para o 5 mais próximo
            min_gain = min_data_gain
            radial_ticks = np.arange(min_gain, max_gain + 1, 5)

        # -------------------------------------------------------------------------

        # Cria o Gráfico
        plt.figure(figsize=(8, 8))
        ax = plt.subplot(111, polar=True)
        
        ax.plot(
            angles_rad, 
            gains_dB, 
            marker='o', 
            linestyle='-',
            color='#087e9e',
            label=f"{freq_text}" 
        )
        
        ax.fill(angles_rad, gains_dB, alpha=0.2, color='#087e9e')
        
        # Uso do Título Fornecido pelo Usuário
        full_title = f"{graph_title}"
        ax.set_title(full_title, va='bottom', fontsize=16, y=1.08) 
        
        # Adiciona a Legenda (para o label definido no ax.plot)
        ax.legend(loc='lower left', bbox_to_anchor=(0.9, 0.9), fontsize=14,borderaxespad=0.) 
        
        ax.set_theta_zero_location('S')
        ax.set_theta_direction(-1)
        ax.set_rlabel_position(135)
        
        # Aplica os limites e as escalas radiais (RTICKS)
        ax.set_rlim(min_gain, max_gain)
        ax.set_rticks(radial_ticks) # <--- APLICA AS ESCALAS AQUI
        ax.grid(True)
        
        # Se temp_path for fornecido, salva a figura para o preview
        if temp_path:
            fig = plt.gcf()
            try:
                fig.savefig(temp_path, format='png', dpi=150)
                plt.close(fig)
            except Exception as e:
                self.manager.get_screen('bluetooth_connection').show_popup_message(f"Erro ao Salvar Figura Temporária: {e}")
        
        return plt.gcf()

    def go_to_save_screen(self):
        """Abre o popup para coletar título e frequência antes de plotar/salvar."""

        if len(powers) < 1:
            message = f"Adicione ao Menos uma Medida\nde Potência para Salvar."
            popup = ConfirmationPopup(message=message)
            popup.open()
            return
        
        # Abre o novo popup para coletar todos os dados (título, freq, escalas)
        popup = PlotInputPopup(plot_action=self.plot_and_navigate_or_preview)
        popup.open()
        
    def preview_graph(self):
        """Abre o popup de input para coletar dados (incluindo escalas) e gerar o preview."""
        if len(powers) < 1:
            message = "Adicione ao Menos uma Medida de Potência para Pré-Visualizar."
            self.manager.get_screen('bluetooth_connection').show_popup_message(message)
            return

        # Abre o popup, a ação de plotagem será definida no popup
        popup = PlotInputPopup(plot_action=self.plot_and_navigate_or_preview)
        popup.open()

    def plot_and_navigate_or_preview(self, graph_title, freq_text, custom_scales, mode):
        """Função central que orquestra a criação do gráfico e decide a ação (Save ou Preview)."""

        if mode == 'preview':
            temp_path = os.path.join(App.get_running_app().user_data_dir, "temp_graph.png")
            self._create_polar_plot(graph_title, freq_text, custom_scales, temp_path=temp_path)
            
            # Exibe o Popup de Visualização
            popup = GraphViewerPopup(image_path=temp_path)
            popup.open()
            
        elif mode == 'save':
            # Cria o plot em memória (sem salvar arquivo temporário)
            self._create_polar_plot(graph_title, freq_text, custom_scales) 
            
            # Navega para a tela de salvamento
            self.manager.current = 'save_file_screen'
            
        else:
            self.manager.get_screen('bluetooth_connection').show_popup_message("Erro no modo de plotagem.")

    def _perform_save(self, path, filename):
        """Salva a figura no caminho e nome de arquivo especificados. (Sem alteração no corpo)"""
        try:
            fig = plt.gcf()
            if not filename.lower().endswith(('.png', '.pdf')):
                filename = f"{filename}.png" #salva como png por padrão
                
            filepath = os.path.join(path, filename)
            file_format = filepath.split('.')[-1]
            folder_name = os.path.basename(path)
            
            fig.savefig(filepath, format=file_format, dpi=300 if file_format == 'png' else None) # Salva o arquivo
            message = f"Arquivo Salvo com sucesso em:\n Pasta: {folder_name}\nNome:  {filename}"
            popup = ConfirmationPopup(message=message)
            popup.open()
            plt.close(fig) # A figura deve ser fechada para funcionar bem no Android
            
        except Exception as e:
            message = f"Erro ao Salvar o Arquivo.\n Tente novamente ou Verifique as Permissões: {e}"
            popup = ConfirmationPopup(message=message)
            popup.open()
            
        self.manager.current = 'motor_control' # Volta a tela
        
    #---------------- Limpar Dados e Iniciar Novo Gráfico ------------------ 
    def limpa_dados(self):
        """Abre o popup de confirmação antes de limpar os dados."""
        popup = ConfirmationDeletePopup(confirm_action=self.limpa_dados_confirmado)
        popup.open()
        
    def limpa_dados_confirmado(self):
        """Executa a limpeza de todos os dados globais, reseta a posição e envia o comando para retornar o motor a 0°"""
        global angles_deg, powers, reference_power
        
        steps_to_zero = int(self.posicao) # Obtém a posição atual
        
        # Limpa os dados globais
        angles_deg = []
        powers = []
        reference_power = None 
        self.posicao = 0
        self.last_slider_value = 0
        self.atualizar_label()
        
        if steps_to_zero > 0:
            command = self._format_command('L', steps_to_zero)
            self.send_bluetooth_data(command)
        else:
            pass
        
        message = "Dados de Potência e Ângulo Excluídos."
        popup_success = ConfirmationPopup(message=message) 
        popup_success.open()
        
    # A função preview_graph original foi substituída e modificada para abrir o PlotInputPopup.
    # O código antigo da preview_graph foi movido para _create_polar_plot e plot_and_navigate_or_preview.

        
# -----------------------------------------------------------------------------------------------------------------------------------
#                                                     CLASSE DE TELA DE SALVAMENTO
# -----------------------------------------------------------------------------------------------------------------------------------
class SaveScreen(Screen):
    """Tela para selecionar o local e nome do arquivo de salvamento."""
    
    path = StringProperty(os.getcwd()) # Propriedades para controle do FileChooser e nome
    filename_text = StringProperty("Diagrama_Radiacao.png")
    
    def save_file(self, path, filename):
        """Chama a função real de salvamento na tela MotorControlScreen."""
        
        if not filename:
            message = f"Nome do Arquivo Não Pode Ser Vazio. \n Insira um Nome Válido"
            popup = ConfirmationPopup(message=message)
            popup.open()
            return
            
        self.manager.get_screen('motor_control')._perform_save(path, filename)

# -----------------------------------------------------------------------------------------------------------------------------------
#                                                          CLASSES AUXILIARES
# -----------------------------------------------------------------------------------------------------------------------------------
class ConfirmationPopup(Popup):
    """Popup simples para mostrar mensagens de confirmação."""
    def __init__(self, message, **kwargs):
        super().__init__(**kwargs)
        self.title = 'ATENÇÃO'
        self.size_hint = (0.7, 0.25)
        self.auto_dismiss = True # Fecha ao clicar fora
        self.content = Label(text=message, halign='center')
        Clock.schedule_once(self.dismiss, 5)#Fecha Após 5 seg
        
class ConfirmationDeletePopup(Popup):
    """Popup de confirmação para exclusão de dados."""
    
    confirm_action = ObjectProperty(None) 
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = 'ATENÇÃO'
        self.size_hint = (0.7, 0.25)
        self.auto_dismiss = False # Não fecha ao clicar fora para garantir a escolha
        
        content_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content_layout.add_widget(Label(text="Deseja Excluir Todos os Dados\ne Retornar a Antena para 0° ?",
                                        halign='center', markup=True))
        
        button_layout = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(40))
        
        from kivy.uix.button import Button # Importa Button se não estiver importado no escopo global
        
        btn_yes = Button(text='Sim', on_release=self.on_yes)
        button_layout.add_widget(btn_yes)
        btn_no = Button(text='Não', on_release=self.dismiss)
        button_layout.add_widget(btn_no)
        
        content_layout.add_widget(button_layout)
        self.content = content_layout

    def on_yes(self, instance):
        """Executa a ação de confirmação e fecha o popup."""
        if self.confirm_action:
            self.confirm_action()
        self.dismiss()

class PlotInputPopup(Popup):
    """Popup para capturar o título do gráfico, a frequência e as escalas radiais personalizadas."""
 
    plot_action = ObjectProperty(None) 
    
    def __init__(self, plot_action, **kwargs):
        super().__init__(**kwargs)
        self.plot_action = plot_action
        self.title = 'DETALHES DO GRÁFICO'
        self.size_hint = (0.8, 0.6) # Aumentado para acomodar o novo campo
        self.auto_dismiss = False
        
        # Cria os TextInputs
        self.title_input = TextInput(
            hint_text='Título do Gráfico', 
            multiline=False, 
            size_hint_y=None, 
            height=dp(40)
        )
        self.freq_input = TextInput(
            hint_text='Frequência (ex: 2.45 GHz)', 
            multiline=False, 
            size_hint_y=None, 
            height=dp(40)
        )
        # Novo campo para escalas radiais
        self.scale_input = TextInput(
            hint_text='Ex: 0, -3, -5, -10, (Separe com vírgulas)', 
            multiline=False, 
            size_hint_y=None, 
            height=dp(40)
        )
        
        content_layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        
        # Campos de entrada
        content_layout.add_widget(Label(text="Título:"))
        content_layout.add_widget(self.title_input)
        content_layout.add_widget(Label(text="Frequência para Legenda:"))
        content_layout.add_widget(self.freq_input)
        
        # Novo campo de Escalas Radiais
        content_layout.add_widget(Label(text="Escalas Radiais (dB):"))
        content_layout.add_widget(self.scale_input)
        
        # Botões
        button_layout = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(40))
        
        # Botão para Pré-Visualização
        btn_preview = Button(
            text='Visualizar', 
            on_release=lambda instance: self.on_confirm(instance, mode='preview')
        )
        # Botão para Plotar e Salvar
        btn_confirm = Button(
            text='Salvar', 
            on_release=lambda instance: self.on_confirm(instance, mode='save')
        )
        
        btn_cancel = Button(text='Voltar', on_release=self.dismiss)
        
        button_layout.add_widget(btn_preview)
        button_layout.add_widget(btn_confirm)
        button_layout.add_widget(btn_cancel)
        
        content_layout.add_widget(button_layout)
        self.content = content_layout

    def on_confirm(self, instance, mode):
        """Passa os dados inseridos para a função de plotagem e fecha o popup."""
        graph_title = self.title_input.text if self.title_input.text else "Diagrama de Radiação"
        freq_text = self.freq_input.text if self.freq_input.text else " "
        
        # Processa as escalas inseridas
        scale_text = self.scale_input.text.replace(' ', '')
        custom_scales = []
        
        try:
            if scale_text:
                # Converte e garante que são números <= 0 (ganho relativo)
                parsed_scales = [float(s) for s in scale_text.split(',') if s.strip()]
                
                # Filtra para garantir que são números razoáveis (ex: <= 0)
                custom_scales = [s for s in parsed_scales if s <= 0]
                
                # Opcional: Limita a 4 (ou mais, dependendo da necessidade, mas o Matplotlib aceita quantos forem)
                # O importante é que a ordenação e o limite sejam tratados na função de plotagem
                custom_scales = list(set(custom_scales)) # Remove duplicatas
                
        except ValueError:
             # Se a conversão falhar, exibe uma mensagem e não usa escalas personalizadas
             popup = ConfirmationPopup(message="Erro no formato das escalas.\nUsando escala automática.")
             popup.open()
             custom_scales = []

        if self.plot_action:
            # Chama a função de plotagem com o novo parâmetro e o modo
            self.plot_action(graph_title, freq_text, custom_scales, mode) 
        self.dismiss()
    

# Sua classe GraphViewerPopup (sem alterações, apenas movida para manter a ordem)
class GraphViewerPopup(Popup):
    """Exibe o gráfico salvo temporariamente, força a atualização e inclui o botão Fechar."""
    def __init__(self, image_path, **kwargs):
        super().__init__(**kwargs)
        self.title = 'Pré-Visualização do Diagrama'
        self.size_hint = (0.9, 0.9) 
        content_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        graph_image = Image(allow_stretch=True, keep_ratio=True)
        graph_image.source = image_path 
        graph_image.reload() 
        content_layout.add_widget(graph_image)
        btn_close = Button(text='Fechar', size_hint_y=None, height=dp(40), on_release=self.dismiss)
        content_layout.add_widget(btn_close)
        self.content = content_layout
        self.bind(on_dismiss=lambda instance: os.remove(image_path))
        
# -----------------------------------------------------------------------------------------------------------------------------------
#                                                     CLASSE PRINCIPAL DO APP
# -----------------------------------------------------------------------------------------------------------------------------------
class MainApp(App):
    def build(self):
        self.title = "Caracterizador de Antenas"
        
        sm = ScreenManager()

        bluetooth_screen = BluetoothScreen(name='bluetooth_connection')
        motor_control_screen = MotorControlScreen(name='motor_control')
        save_screen = SaveScreen(name='save_file_screen')
        
        sm.add_widget(bluetooth_screen)
        sm.add_widget(motor_control_screen)
        sm.add_widget(save_screen)
        
        sm.current = 'bluetooth_connection'

        return sm


if __name__ == "__main__":
    pedir_permissoes_bluetooth() 

    MotorControlScreen.passo.defaultvalue = 1
    MainApp().run()