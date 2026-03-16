# Ant_Game

## 依赖
 - gcc/g++版本: 9.4.0

## 运行
使用Linux CMake, 已由 Create C++ Project自动生成Makefile文件, 暂时不考虑修改
运行直接使用make命令
```
make
```

## 代码结构
```
ant_game/
    include/ 存放头文件
    
    lib/ 存放静态链接文件
    
    output/ 可执行文件

    src/ cpp文件
        main.cpp

    Makefile
```

## 其它
commit 时临时文件删除
```
make clean
```

### 本地judger
python judger.py <Logic> <AI>