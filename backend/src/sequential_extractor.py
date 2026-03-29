import re

class SequentialExtractor:
    def __init__(self, band_string):
        self.band_string = band_string
        self.eutra_bands = self.extract_bands('EUTRA')
        self.nr_bands = self.extract_bands('NR')

    def extract_bands(self, type):
        pattern = self.get_pattern(type)
        bands = re.findall(pattern, self.band_string)
        return bands

    def get_pattern(self, type):
        if type == 'EUTRA':
            return r'\b(1[0-9]{1}|2[0-9]{1}|3[0-9]{1}|4[0-9]{1}|5[0-9]{1}|6[0-9]{1}|7[0-9]{1}|8[0-9]{1}|9[0-9]{1}|10[0-9]{1}|11[0-9]{1}|12[0-9]{1}|13[0-9]{1}|14[0-9]{1}|15[0-9]{1}|16[0-9]{1}|17[0-9]{1}|18[0-9]{1}|19[0-9]{1}|20[0-9]{1})\b'
        elif type == 'NR':
            return r'\b(2600|4100|4200|4700|4800|4900|5000|5100|6000|7000|8000)\b'
        return ''

    def display_extracted_bands(self):
        print(f'EUTRA Bands: {self.eutra_bands}')
        print(f'NR Bands: {self.nr_bands}')

# Example Usage:
# extractor = SequentialExtractor('Some input string with bands 1, 3, 20, 2600')
# extractor.display_extracted_bands()