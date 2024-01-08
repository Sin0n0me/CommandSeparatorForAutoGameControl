import re
import pynput
from enum import Enum
from datetime import datetime, timedelta

TIME_MATCH =  re.compile(r'(\d+):(\d+).(\d+)')

class ControlCommand(Enum):
    KEY_DOWN = 'KeyDown'
    SPECIAL_KEY_DOWN = 'SPKeyDown'
    STRING = 'String'
    GAMEPAD_BUTTON = 'GamePadButton'
    GAMEPAD_STICK = 'GamePadStick'
    MOUSE_CLICK = 'MouseClick'
    MOUSE_CURSOR = 'MouseCursor'
    MOUSE_SCROLL = 'MouseScroll'
    CAPTURE = 'Capture'
    IF = 'if'
    ELSE = 'else'
    FI = 'fi'

class ControlSubCommand(Enum):
    MOUSE_CURSOR_ACTION_MOVE = 'Move'
    MOUSE_CURSOR_ACTION_VECTOR = 'Vector'    

class CommandSeparater(): 

    # コマンドとして解釈できないものは全てNoneで返す
    @staticmethod
    def get_command(line:str):
        line = line.replace('\n','')

        # コマンドの定義に従っているかチェック
        semicolon_pos = line.find(';')
        if semicolon_pos == -1 and line.find(':') == -1:
            return (None, None, None)
    
        # 開始時間, コマンド, 引数に分割する
        start_time = None
        command = ''
        args = ''
                    
        # セミコロンがない場合は条件式
        if semicolon_pos == -1:
            full_command = line
        else:
            start_time, full_command = line.strip().split(';', 1)
            match = TIME_MATCH.match(start_time)
            
            if match:
                minutes, seconds, milli_seconds = match.groups()
                # 分、秒、ミリ秒を整数型に変換
                minutes = int(minutes)
                seconds = int(seconds)
                milli_seconds = int(milli_seconds)
                start_time = timedelta(minutes=minutes, seconds=seconds, milliseconds=milli_seconds)
            else:
                return (None, None, None)

        command, args = full_command.strip().split(":", 1)
        
        # コメント部分の切り取り
        args = CommandSeparater.slice_comment(args)
        
        return (start_time, command, args)

    @staticmethod 
    def in_command(line:str):
        start_time, command, args = CommandSeparater.get_command(line)        
        if not command:
            return False
        return CommandSeparater.is_valid_command(command)

    @staticmethod 
    def is_valid_command(command:str):        
        for i in ControlCommand:
            if i.value == command:
                return True
        
        return False
    
    @staticmethod 
    def split_time(line:str):
        if line.find(';') == -1:
            return (None, None)
        
        start_time, full_command = line.strip().split(';', 1)
        return (start_time, full_command)
    
    @staticmethod
    def slice_comment(args:str) -> str:
        # コメントアウトチェック    
        # 引数部分はキーかコメントか不明なので切り分け
        # 1つの場合は:直後に存在するか(スペースは含まない)で判定する
        args_shape_pos = args.find('#')
        if args_shape_pos != -1:
            
            # 2つ以上#が存在する場合は2つ目以降をコメントアウトとする
            slice_pos = len(args)
            args_shape_pos2 = args[args_shape_pos + 1:].find('#') # +1しなければ最初の#が含まれる
            if args_shape_pos2 == -1:
                # タブもしくはスペース以外が存在した場合は#押下ではない
                is_key_down_shape = True
                for c in args[:args_shape_pos]:
                    if c != ' ' or c != '\t':
                        is_key_down_shape = False
                        break
                
                # #キーでない場合は#以降を切り取り
                if not is_key_down_shape:
                    slice_pos = args_shape_pos
            else:
                slice_pos = args_shape_pos + args_shape_pos2 + 1

            #print(f'comment:{args[slice_pos:]}')
            args = args[:slice_pos]    
            
        return args    

    @staticmethod
    def get_key_args(command:str, args:str):
        # 押下するキーの切り抜き
        key = args.split()[0]

        # 装飾キーの切り抜き
        modify_keys = [] if command.find('+') == -1 else command.split('+')[1:]    

        # 押下時間のチェック
        duration = args.split()[-1] if len(args.split()) > 1 else None        
        
        return (key, modify_keys, duration)

    @staticmethod
    def get_mouse_cursor_args(args:str):
        split_args = args.split()
        action, x, y = split_args[:3]
        x, y = int(x), int(y)
        duration = split_args[3] if len(split_args) > 3 else 0
        duration = int(duration) / 1000
        
        return (action, x, y, duration)
        
    @staticmethod
    def format_time(elapsed_time:timedelta) -> str:
        # 分(MM)と秒(SS.SS)を計算
        total_seconds = elapsed_time.total_seconds()
        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60

        # MM:SS.SS 形式にフォーマット
        return f'{minutes:02}:{seconds:05.2f}'

    @staticmethod
    def fomat_command(elapsed_time:timedelta, command:str, args:str):
        formatted_time = CommandSeparater.format_time(elapsed_time)        
        return f'{formatted_time};{command}:{args}'

    @staticmethod
    def format_command_key_down(formatted_time:str, key, milli_second:int=0):
        if isinstance(key, pynput.keyboard.Key):
            command = ControlCommand.SPECIAL_KEY_DOWN
            press_key = key.name
        elif isinstance(key, pynput.keyboard.KeyCode):
            command = ControlCommand.KEY_DOWN
            if key.char:
                press_key = key.char
            else:
                # 仮想キーコードの変換を行いたい
                press_key = key.vk
        else:
            raise RuntimeError()
        
        return CommandSeparater.fomat_command(
            elapsed_time=formatted_time,
            command=command,
            args=f'{press_key} {milli_second}'
            )

    @staticmethod
    def format_command_mouse_move(formatted_time:timedelta, x, y):
        return CommandSeparater.fomat_command(
            elapsed_time=formatted_time,
            command=ControlCommand.MOUSE_CURSOR,
            args=f'{x} {y}'
            )

    @staticmethod
    def format_command_mouse_click(formatted_time:timedelta, x, y, milli_second:int=0):
        return CommandSeparater.fomat_command(
            elapsed_time=formatted_time,
            command=ControlCommand.MOUSE_CLICK,
            args=f'{ControlSubCommand.MOUSE_CURSOR_ACTION_MOVE} {x} {y} {milli_second}'
            )

    @staticmethod
    def format_command_gamepad_button(formatted_time:timedelta, button, milli_second:int=0):        
        return CommandSeparater.fomat_command(
            elapsed_time=formatted_time,
            command=ControlCommand.GAMEPAD_BUTTON,
            args=f'{button} {milli_second}'
            )

    @staticmethod
    def format_command_gamepad_joystick(formatted_time:timedelta, stick_num, x, y):
        return CommandSeparater.fomat_command(
            elapsed_time=formatted_time,
            command=ControlCommand.GAMEPAD_STICK,
            args=f'{stick_num} {x} {y}'
            )

