"""
Linux SysFS-based native GPIO implementation.

The MIT License (MIT)

Copyright (c) 2014 Derek Willian Stavis

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import sys, os, select

from twisted.internet import reactor

import logging

Logger = logging.getLogger('sysfs.gpio')

class GPIOPinDirection:
    """ 
    Enumerates signal directions
    """

    def __init__(self):
        raise RuntimeError("You should not instantiate this class")

    INPUT   = 0
    OUTPUT  = 1
    all     = [INPUT, OUTPUT]

class GPIOPinEdge:
    """ 
    Enumerates signal edge detection
    """

    def __init__(self):
        raise RuntimeError("You should not instantiate this class")
    
    RISING  = 0
    FALLING = 1
    BOTH    = 3

class GPIOPin(object):
    """
    Represent a pin in SysFS
    """

    SYSFS_GPIO_PATH     = '/sys/class/gpio/gpio%d'

    SYSFS_GPIO_DIRECTION_PATH = SYSFS_GPIO_PATH + '/direction'
    SYSFS_GPIO_EDGE_PATH      = SYSFS_GPIO_PATH + '/edge'
    SYSFS_GPIO_VALUE_PATH     = SYSFS_GPIO_PATH + '/value'

    SYSFS_GPIO_EDGE_NONE    = 'none'
    SYSFS_GPIO_EDGE_RISING  = 'rising'
    SYSFS_GPIO_EDGE_FALLING = 'falling'
    SYSFS_GPIO_EDGE_BOTH    = 'both'

    SYSFS_GPIO_DIRECTION_OUT  = 'out'
    SYSFS_GPIO_DIRECTION_IN   = 'in'

    SYSFS_GPIO_VALUE_LOW   = '0'
    SYSFS_GPIO_VALUE_HIGH  = '1'

    def __init__(self, number, direction, callback=None, edge=None):
        """
        @type  number: int
        @param number: The pin number
        @type  direction: int
        @param direction: Pin direction, enumerated by C{GPIOPinDirection}
        @type  callback: callable
        @param callback: Method be called when pin changes state
        @type  edge: int
        @param edge: The edge transition that triggers callback, 
                     enumerated by C{GPIOPinEdge}
        """
        if direction not in GPIOPinDirection.all:
            raise Exception("Pin direction %s not in GPIOPinDirection.all" % direction)
            return

        self._number = number
        self._direction = direction
        self._callback  = callback

        self._fd = open(self._get_sysfs_gpio_value_path(), 'r+')
        self._edge = edge

        if callback is not None and edge is None:
            raise Exception('You must supply a edge to trigger callback on')

        with open(self._get_sysfs_gpio_direction_path(), 'w') as fsdir:

            if direction is GPIOPinDirection.OUTPUT:
                fsdir.write(self.SYSFS_GPIO_DIRECTION_OUT)

            elif direction is GPIOPinDirection.INPUT:
                fsdir.write(self.SYSFS_GPIO_DIRECTION_IN)

        with open(self._get_sysfs_gpio_edge_path(), 'w') as fsedge:

            if edge is GPIOPinEdge.BOTH:
                fsedge.write(self.SYSFS_GPIO_EDGE_BOTH)
            elif edge is GPIOPinEdge.RISING:
                fsedge.write(self.SYSFS_GPIO_EDGE_RISING)
            elif edge is GPIOPinEdge.FALLING:
                fsedge.write(self.SYSFS_GPIO_EDGE_FALLING)

    @property
    def callback(self):
        """
        Gets this pin callback
        """
        return self._callback
    @callback.setter
    def callback(self, value):
        """
        Sets this pin callback
        """
        self._callback = value

    @property
    def direction(self):
        """
        Pin direction
        """
        return self._direction

    @property
    def number(self):
        """
        Pin number
        """
        return self._number

    def set(self):
        """
        Set pin to HIGH logic setLevel
        """
        self._fd.write(self.SYSFS_GPIO_VALUE_HIGH)
        self._fd.seek(0)

    def reset(self):
        """
        Set pin to LOW logic setLevel
        """
        self._fd.write(self.SYSFS_GPIO_VALUE_LOW)
        self._fd.seek(0)

    def read(self):
        """
        Read pin value

        @rtype: int
        @return: I{0} when LOW, I{1} when HIGH
        """
        val = self._fd.read()
        self._fd.seek(0)
        return int(val)

    def fileno(self):
        """
        Get the file descriptor associated with this pin.

        @rtype: int
        @return: File descriptor
        """
        return self._fd.fileno()

    def changed(self, state):
        if callable(self._callback):
            self._callback(self.number, state)

    def _get_sysfs_gpio_value_path(self):
        """
        Get the file that represent the value of this pin.
        
        @rtype: str
        @return: the path to sysfs value file
        """
        return self.SYSFS_GPIO_VALUE_PATH % self.number

    def _get_sysfs_gpio_direction_path(self):
        """
        Get the file that represent the direction of this pin.

        @rtype: str
        @return: the path to sysfs direction file
        """
        return self.SYSFS_GPIO_DIRECTION_PATH % self.number

    def _get_sysfs_gpio_edge_path(self):
        """
        Get the file that represent the edge that will trigger an interrupt.

        @rtype: str
        @return: the path to sysfs edge file
        """
        return self.SYSFS_GPIO_EDGE_PATH % self.number


class GPIOController(object):
    '''
    A singleton class to provide access to SysFS GPIO pins
    '''

    SYSFS_GPIO_PATH     = '/sys/class/gpio/gpio%d'

    SYSFS_EXPORT_PATH   = '/sys/class/gpio/export'
    SYSFS_UNEXPORT_PATH = '/sys/class/gpio/unexport'

    EVENT_LOOP_INTERVAL = 0.01

    def __new__(cls, *args, **kw):
        if not hasattr(cls, '_instance'):
            instance = super(GPIOController, cls).__new__(cls, args, kw)
            instance._allocated_pins = {}
            instance._poll_queue = select.epoll()

            instance._available_pins = []
            instance._running = True

            reactor.addSystemEventTrigger(
                'before', 'shutdown',
                instance.stop
            )

            # Run the EPoll in a Thread, as it blocks.
            reactor.callInThread(instance._poll_queue_loop)

            cls._instance = instance
        return cls._instance

    def __init__(self):
        pass

    def _poll_queue_loop(self):

        while self._running:
            events = self._poll_queue.poll(1)
            if len(events) > 0:
                reactor.callFromThread(self._poll_queue_event, events)

    @property
    def available_pins(self):
        return self._available_pins
    @available_pins.setter
    def available_pins(self, value):
        self._available_pins = value
        
    def stop(self):
        self._running = False

        for pin in self._allocated_pins.copy().itervalues():
            self.dealloc_pin(pin.number)

    def alloc_pin(self, number, direction, callback=None, edge=None):

        Logger.debug('SysfsGPIO: alloc_pin(%d, %d, %s, %s)' % (number, direction, callback, edge))

        self._check_pin_validity(number)

        if direction not in GPIOPinDirection.all:
            raise Exception("direction not in GPIOPinDirection")
            return

        if not self._check_pin_already_exported(number):

            with open(self.SYSFS_EXPORT_PATH, 'w') as export:
                export.write('%d' % number)

        else:

            Logger.debug("SysfsGPIO: Pin %d already exported" % number)

        pin = GPIOPin(number, direction, callback, edge)

        self._allocated_pins[number] = pin

        if direction is GPIOPinDirection.INPUT:
            self._poll_queue_register_pin(pin)

        return pin

    def _poll_queue_register_pin(self, pin):
        ''' GPIOPin responds to fileno(), so it's pollable. '''
        self._poll_queue.register(pin, (select.EPOLLPRI | select.EPOLLET))

    def _poll_queue_unregister_pin(self, pin):
        self._poll_queue.unregister(pin)

    def dealloc_pin(self, number):

        Logger.debug('SysfsGPIO: dealloc_pin(%d)' % number)

        if number not in self._allocated_pins:
            raise Exception('Pin %d not allocated' % number)

        with open(self.SYSFS_UNEXPORT_PATH, 'w') as unexport:
            unexport.write('%d' % number)

        pin = self._allocated_pins[number]

        if pin.direction is GPIOPinDirection.INPUT:
            self._poll_queue_unregister_pin(pin)

        del pin, self._allocated_pins[number]

    def get_pin(self, number):

        Logger.debug('SysfsGPIO: get_pin(%d)' % number)

        return self._allocated_pins[number]

    def set_pin(self, number):

        Logger.debug('SysfsGPIO: set_pin(%d)' % number)

        if number not in self._allocated_pins:
            raise Exception('Pin %d not allocated' % number)

        return self._allocated_pins[number].set()

    def reset_pin(self, number):

        Logger.debug('SysfsGPIO: reset_pin(%d)' % number)

        if number not in self._allocated_pins:
            raise Exception('Pin %d not allocated' % number)

        return self._allocated_pins[number].reset()

    def get_pin_state(self, number):

        Logger.debug('SysfsGPIO: get_pin_state(%d)' % number)

        if number not in self._allocated_pins:
            raise Exception('Pin %d not allocated' % number)

        pin = self._allocated_pins[number]

        if pin.direction == GPIOPinDirection.INPUT:
            self._poll_queue_unregister_pin(pin)

        val = pin.read()

        if pin.direction == GPIOPinDirection.INPUT:
            self._poll_queue_register_pin(pin)

        if val <= 0:
            return False
        else:
            return True

    ''' Private Methods '''

    def _poll_queue_event(self, events):
        """
        EPoll event callback
        """
        
        for fd, event in events:
            if not (event & (select.EPOLLPRI | select.EPOLLET)): continue

            for pin in self._allocated_pins.itervalues():
                if pin.fileno() == fd:
                    pin.changed(pin.read())

    def _check_pin_already_exported(self, number):
        """
        Check if this pin was already exported on sysfs.

        @type  number: int
        @param number: Pin number
        @rtype: bool
        @return: C{True} when it's already exported, otherwise C{False}
        """
        gpio_path = self.SYSFS_GPIO_PATH % number
        return os.path.isdir(gpio_path)

    def _check_pin_validity(self, number):
        """
        Check if pin number exists on this bus

        @type  number: int
        @param number: Pin number
        @rtype: bool
        @return: C{True} when valid, otherwise C{False}
        """

        if number not in self._available_pins:
            raise Exception("Pin number out of range")
            return

        if number in self._allocated_pins:
            raise Exception("Pin already allocated")
            return

if __name__ ==  '__main__':
    print("This module isn't intended to be run directly.")
