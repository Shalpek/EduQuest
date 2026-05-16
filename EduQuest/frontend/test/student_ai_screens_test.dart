import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:frontend/screens/ai_review_screen.dart';
import 'package:frontend/screens/ai_tutor_screen.dart';
import 'package:frontend/ui/eduquest_theme.dart';

void main() {
  testWidgets('AITutorScreen sends grounded lesson question', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildEduQuestTheme(),
        home: AITutorScreen(
          userId: 1,
          courseId: 1,
          courseTitle: 'Intro to CS',
          lessonId: 2,
          lessonTitle: 'Variables',
          createSession: (_, __, ___) async => {'session_id': 77},
          sendMessage:
              (_, message) async => {
                'answer': 'Grounded reply for $message',
              },
        ),
      ),
    );

    await tester.pumpAndSettle();
    expect(find.text('Variables'), findsOneWidget);
    expect(find.text('Intro to CS'), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'Explain it simply');
    await tester.tap(find.byIcon(Icons.send));
    await tester.pumpAndSettle();

    expect(find.text('Explain it simply'), findsOneWidget);
    expect(find.text('Grounded reply for Explain it simply'), findsOneWidget);
  });

  testWidgets('AIReviewScreen loads attempt explanations and follow-up chat', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildEduQuestTheme(),
        home: AIReviewScreen(
          userId: 1,
          attemptId: 9,
          lessonTitle: 'Control Flow',
          createSession:
              (_, __, ___) async => {
                'session_id': 15,
                'summary': 'I found 1 incorrect answer.',
                'explanations': [
                  {
                    'question': 'Which statement helps a program choose?',
                    'your_answer': 'list',
                    'correct_answer': 'if',
                    'explanation': 'The question is about conditional branching.',
                    'why_your_answer_was_wrong':
                        'A list stores data, but it does not choose execution paths.',
                    'why_correct_answer_is_correct':
                        'The if statement chooses between branches based on a condition.',
                    'lesson_connection': 'Conditionals choose between branches.',
                  },
                ],
              },
          sendMessage:
              (_, message) async => {
                'answer': 'Follow-up for $message',
                'summary': 'I found 1 incorrect answer.',
                'explanations': [
                  {
                    'question': 'Which statement helps a program choose?',
                    'your_answer': 'list',
                    'correct_answer': 'if',
                    'explanation': 'The question is about conditional branching.',
                    'why_your_answer_was_wrong':
                        'A list stores data, but it does not choose execution paths.',
                    'why_correct_answer_is_correct':
                        'The if statement chooses between branches based on a condition.',
                    'lesson_connection': 'Conditionals choose between branches.',
                  },
                ],
              },
        ),
      ),
    );

    await tester.pumpAndSettle();
    expect(find.text('I found 1 incorrect answer.'), findsOneWidget);
    expect(find.text('Correct answer: if'), findsOneWidget);
  });
}
