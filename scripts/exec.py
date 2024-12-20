import subprocess
import os

# Caminhos para os scripts
recon_script_path = os.path.join(os.path.dirname(__file__), "Outros/Recon.py")
audio_script_path = os.path.join(os.path.dirname(__file__), "Outros/Audio.py")
joystick_script_path = os.path.join(os.path.dirname(__file__), "Outros/Joystick.py")

# Função para executar um script Python
def run_script(script_path):
    try:
        # Utiliza subprocess para rodar o script
        subprocess.run(["python3", script_path], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Erro ao executar o script {script_path}: {e}")

# Menu para selecionar qual script executar
def main():
    while True:
        print("Selecione qual script deseja executar:")
        print("1 - Executar Recon.py")
        print("2 - Executar Audio.py")
        print("3 - Executar Joystick.py")
        print("0 - Sair")
        
        escolha = input("Digite o número da sua escolha: ")

        if escolha == "1":
            print("Executando Recon.py...")
            run_script(recon_script_path)
        elif escolha == "2":
            print("Executando Audio.py...")
            run_script(audio_script_path)
        elif escolha == "3":
            print("Executando Joystick.py...")
            run_script(joystick_script_path)

        elif escolha == "0":
            print("Saindo...")
            break
        else:
            print("Opção inválida. Por favor, tente novamente.")

if __name__ == "__main__":
    main()
