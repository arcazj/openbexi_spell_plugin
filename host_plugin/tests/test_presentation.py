"""The neutral GUI protocol preserves native values and prompt answer indices."""
import unittest
from openbexi_spell_host.presentation import presentation


def convert(event, **body):
    return presentation(dict(type='event', event=event, body=body))['body']


class PresentationTests(unittest.TestCase):
    def test_native_choice_labels_do_not_replace_answer_indices(self):
        event = convert('spell/prompt', promptId='one', ProcId='child#1', DataType='64',
                        Text='Choose', ExpectedValues='Y\4N', OptionValues='Yes\4No')
        self.assertEqual(event['choices'], [dict(label='Yes', value='0'), dict(label='No', value='1')])
        self.assertEqual(event['procedureId'], 'child#1')

    def test_password_default_is_not_exposed_in_a_hint(self):
        event = convert('spell/prompt', promptId='secret', DataType='4096', DefaultProvided='True', Default='hidden')
        self.assertEqual(event['inputType'], 'password')
        self.assertNotIn('defaultHint', event)

    def test_unreported_results_remain_empty_and_native_values_are_preserved(self):
        event = convert('spell/notification', DataType='CURRENT_LINE', source={'path': '/project/main.py'}, line=2,
                        ProcId='main#0', rootProcedureId='main#0', Time='2026-10-17 12:00:00')
        self.assertTrue(event['current'])
        self.assertEqual(event['status'], '')
        self.assertEqual(event['timestamp'], '2026-10-17 12:00:00')
        self.assertIsNone(presentation(dict(type='event', event='spell/notification', body={'DataType': 'ITEM'})))


if __name__ == '__main__':
    unittest.main()
