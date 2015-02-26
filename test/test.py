from jep.config import find_service_config


sc = find_service_config('test/test.rb')
print(sc.command, sc.file, sc.patterns)

sc = find_service_config('test/test.txt')
print(sc.command, sc.file, sc.patterns)

sc = find_service_config('test/test.c')
print(sc)
