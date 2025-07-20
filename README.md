# ZFS Monitor

ZFS Monitor é uma aplicação gráfica em Python com GTK3 para monitoramento em tempo real de pools ZFS. Ele exibe status, desempenho e alertas em uma interface com abas, além de um ícone na bandeja do sistema para fácil acesso.

## Funcionalidades

- **Interface Gráfica com GTK3**: Layout limpo e responsivo.
- **Monitoramento em Tempo Real**: Utiliza `zpool status` e `zpool iostat` para fornecer informações atualizadas.
- **Alertas Visuais**: Destaca automaticamente problemas detectados no pool.
- **Integração com a Bandeja do Sistema**: Ícone de notificação permite acesso rápido à aplicação.
- **Ativação sob Demanda**: Funciona apenas quando a variável de ambiente `ZPOOL_MONITOR_ENABLE` estiver definida.

## Pré-requisitos

- **Sistema Operacional**: Debian 12 (Bookworm) ou distribuições derivadas (Ubuntu 22.04, Linux Mint 21).
- **ZFS**: Instalar o pacote `zfsutils-linux` e configurar um pool ZFS.
- **Pacotes Python e GTK**:
  - `python3.11`
  - `python3-gi`
  - `gir1.2-gtk-3.0`
  - `gir1.2-ayatanaappindicator3-0.1`

## Instalação

### 1. Clonar o Repositório

```bash
git clone https://github.com/seu-usuario/zfs-monitor.git
cd zfs-monitor
````

### 2. Instalar Dependências

```bash
sudo apt update
sudo apt install python3.11 python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 zfsutils-linux
```

### 3. Executar o Monitor

```bash
chmod +x zfs-monitor.py
ZPOOL_MONITOR_ENABLE=1 python3.11 ./zfs-monitor.py
```

## Execução Automática

Para que o monitor seja iniciado junto com o sistema, crie um atalho `.desktop` em `~/.config/autostart/`.

## Personalização

### Nome do Pool

Edite o valor da variável `POOL_NAME` no código-fonte para corresponder ao seu pool ZFS:

```python
POOL_NAME = "zhome"
```

### Ícone da Bandeja

O ícone exibido pode ser alterado substituindo o nome `"drive-harddisk"` por outro nome de ícone disponível no seu tema de ícones do sistema.

## Solução de Problemas

### Erro: ModuleNotFoundError: No module named 'gi'

**Causa**: Versão incorreta do Python.

**Solução**: Execute com a versão correta:

```bash
ZPOOL_MONITOR_ENABLE=1 python3.11 ./zfs-monitor.py
```

### Erro: Pacote `gir1.2-appindicator3-0.1` não encontrado

**Causa**: O pacote foi substituído por `ayatanaappindicator`.

**Solução**:

```bash
sudo apt install gir1.2-ayatanaappindicator3-0.1
```

### O script não inicia ou não apresenta interface

**Causa**: A variável de ambiente `ZPOOL_MONITOR_ENABLE` não está definida.

**Solução**:

```bash
ZPOOL_MONITOR_ENABLE=1 ./zfs-monitor.py
```

## Contribuições

Contribuições são bem-vindas! Sinta-se à vontade para abrir *Pull Requests* com melhorias, correções de bugs ou novas funcionalidades.

## Licença

Este projeto está licenciado sob os termos da licença MIT. Consulte o arquivo `LICENSE` para mais detalhes.

## Autor

Seu Nome
[GitHub](https://github.com/mvdiogo)
[LinkedIn](https://linkedin.com/in/mvdiogoce)
