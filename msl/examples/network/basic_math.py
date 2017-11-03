import time
import logging

from msl.network import Service


class BasicMath(Service):

    name = 'Basic Math'

    label = 'my label'

    @property
    def seven(self):
        log.info('called the "seven" property')
        return 7

    def add(self, x: int, y: int) -> int:
        log.info('add -- waiting for 1 second')
        time.sleep(1)
        return x + y

    def subtract(self, x: int, y: int) -> int:
        log.info('subtract -- waiting for 2 seconds')
        time.sleep(2)
        return x - y

    def multiply(self, x: float, y: float) -> float:
        log.info('multiply -- waiting for 3 seconds')
        time.sleep(3)
        return x * y

    def divide(self, x: float, y: float) -> float:
        log.info('divide -- waiting for 4 seconds')
        time.sleep(4)
        return x / float(y)

    def error_if_negative(self, x: float) -> bool:
        log.info('error_if_negative -- waiting for 5 seconds')
        time.sleep(5)
        if x < 0:
            raise ValueError('The value is < 0')
        return True

    def power(self, x: float, n=2) -> float:
        log.info('power -- waiting for 6 seconds')
        time.sleep(6)
        return x ** n


if __name__ == '__main__':

    debug = True

    log = logging.getLogger('basic_math')
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format='%(asctime)s [%(levelname)-5s] %(name)s - %(message)s',
    )

    service = BasicMath()
    service.start(debug=debug)
