Linux SysFS GPIO access via Python
==================================

This package offer Python classes to work with GPIO on Linux.

## Core Requirements

As this pacakge relies on modern techniques provided by Linux kernel,
your kernel version should support at least EPoll and SysFS interfaces.

## Package Requirements

This package is based on Twisted main loop. To build the package you will also
need setuptools.

## How to use it

1. Download this repository

```shell
    git clone https://github.com/derekstavis/python-sysfs-gpio.git
```

2. Inside it, issue:

```shell
    sudo python setup.py install
```

3. On your code:

```python

    # Import Twisted mainloop
    
    from twisted.internet import reactor
    
    # Import this package objects
    
    from sysfs.gpio import GPIOController
    from sysfs.gpio import GPIOPinDirection as Direction
    from sysfs.gpio import GPIOPinEdge as Edge
    
    # Refer to your chip GPIO numbers and set them here
    
    GPIOController().available_pins = [1, 2, 3, 4] 
    
    # Allocate a pin as Output signal
    
    pin = GPIOController().alloc_pin(1, Direction.OUTPUT)
    pin.set()   # Sets pin to high logic level
    pin.reset() # Sets pin to low logic level
    pin.read()  # Reads pin logic level
    
    # Allocate a pin as simple Input signal
    
    pin = GPIOController().alloc_pin(1, Direction.INPUT)
    pin.read()  # Reads pin logic level
    
    # Allocate a pin as level triggered Input signal
    
    def pin_changed(state):
        print("Pin changed to %d state" % state)
    
    pin = GPIOController().alloc_pin(1, Direction.INPUT, changed, Edge.RISING)
    pin.read()  # Reads pin logic level

```

4. Don't forget to start reactor loop!

```python
    reactor.run()
```


## Contributing

If you think that there's work that can be done to make this module better 
(and that's the only certainty), fork this repo, make some changes and create
a pull request. I will be glad to accept it! :)
