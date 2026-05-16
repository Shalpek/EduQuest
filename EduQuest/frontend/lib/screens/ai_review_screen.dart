import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../ui/app_components.dart';
import '../ui/eduquest_theme.dart';

typedef CreateQuizExplanationSession =
    Future<Map<String, dynamic>?> Function(
      int attemptId,
      int? questionIndex,
      String? message,
    );
typedef SendQuizExplanationMessage =
    Future<Map<String, dynamic>?> Function(int sessionId, String message);

class AIReviewScreen extends StatefulWidget {
  final int userId;
  final int attemptId;
  final String lessonTitle;
  final int? questionIndex;
  final CreateQuizExplanationSession? createSession;
  final SendQuizExplanationMessage? sendMessage;

  const AIReviewScreen({
    required this.userId,
    required this.attemptId,
    required this.lessonTitle,
    this.questionIndex,
    this.createSession,
    this.sendMessage,
    super.key,
  });

  @override
  State<AIReviewScreen> createState() => _AIReviewScreenState();
}

class _AIReviewScreenState extends State<AIReviewScreen> {
  final TextEditingController _questionController = TextEditingController();
  final List<Map<String, String>> _messages = [];

  Map<String, dynamic>? _reviewData;
  bool _isLoading = true;
  bool _isTyping = false;
  int? _sessionId;
  String? _error;

  CreateQuizExplanationSession get _createSession =>
      widget.createSession ??
      ((attemptId, questionIndex, message) =>
          ApiService.createQuizExplanationSession(
            attemptId,
            questionIndex: questionIndex,
            message: message,
          ));

  SendQuizExplanationMessage get _sendMessageRequest =>
      widget.sendMessage ?? ApiService.sendQuizExplanationMessage;

  @override
  void initState() {
    super.initState();
    _loadReview();
  }

  Future<void> _loadReview() async {
    final review = await _createSession(
      widget.attemptId,
      widget.questionIndex,
      null,
    );

    if (!mounted) return;

    setState(() {
      _reviewData = review;
      _isLoading = false;
      _sessionId = review?['session_id'] as int?;
      if (review == null) {
        _error =
            'The AI review session could not be created. Check the backend and retry.';
      } else {
        _messages.add({
          'role': 'ai',
          'text':
              review['summary']?.toString() ??
              'I reviewed your completed quiz attempt. Ask about any incorrect answer.',
        });
      }
    });
  }

  Future<void> _sendQuestion() async {
    final prompt = _questionController.text.trim();
    if (prompt.isEmpty || _isTyping || _sessionId == null) return;

    setState(() {
      _messages.add({'role': 'user', 'text': prompt});
      _questionController.clear();
      _isTyping = true;
    });

    final response = await _sendMessageRequest(_sessionId!, prompt);
    if (!mounted) return;

    setState(() {
      if (response == null || response['answer'] == null) {
        _messages.add({
          'role': 'ai',
          'text':
              'I could not generate a quiz explanation right now. Please try again.',
        });
        _error = 'No AI explanation was returned by the backend.';
      } else {
        _messages.add({'role': 'ai', 'text': response['answer'].toString()});
        _reviewData = response;
        _error = null;
      }
      _isTyping = false;
    });
  }

  @override
  void dispose() {
    _questionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        body: AppLoadingView(
          title: 'Preparing AI explanation',
          message:
              'Loading the completed attempt, its mistakes, and grounded lesson context.',
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('AI Teacher Review')),
      resizeToAvoidBottomInset: true,
      body: SafeArea(
        top: false,
        child: Column(
          children: [
            Expanded(
              child: ListView(
                keyboardDismissBehavior:
                    ScrollViewKeyboardDismissBehavior.onDrag,
                padding: const EdgeInsets.all(16),
                children: [
                  _buildIntroCard(),
                  const SizedBox(height: 16),
                  const AppSectionHeader(
                    title: 'Incorrect answers explained',
                    subtitle:
                        'These cards come from the completed server-side attempt snapshot, not from client-only quiz state.',
                  ),
                  const SizedBox(height: 12),
                  ..._buildExplanationCards(),
                  const SizedBox(height: 16),
                  const AppSectionHeader(
                    title: 'Ask the AI teacher',
                    subtitle:
                        'Use follow-up questions to clarify the exact quiz mistakes you just reviewed.',
                  ),
                  const SizedBox(height: 12),
                  ..._messages.map(_buildMessageBubble),
                  if (_isTyping) _buildTypingIndicator(),
                ],
              ),
            ),
            _buildComposer(),
          ],
        ),
      ),
    );
  }

  Widget _buildIntroCard() {
    return AppSurface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              const AppInfoChip(
                label: 'Completed attempt only',
                color: EduQuestColors.info,
                icon: Icons.smart_toy_outlined,
              ),
              AppInfoChip(
                label:
                    '${(_reviewData?['explanations'] as List<dynamic>? ?? []).length} answers to review',
                color: EduQuestColors.secondary,
                icon: Icons.rule_folder_outlined,
              ),
              if (widget.questionIndex != null)
                AppInfoChip(
                  label: 'Focused on question ${widget.questionIndex! + 1}',
                  color: EduQuestColors.primary,
                  icon: Icons.filter_1_outlined,
                ),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            widget.lessonTitle,
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          Text(
            _reviewData?['summary']?.toString() ??
                'The AI teacher prepared structured explanations for each mistake.',
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            AppStatusBanner(
              message: _error!,
              color: EduQuestColors.danger,
              icon: Icons.error_outline,
            ),
          ],
        ],
      ),
    );
  }

  List<Widget> _buildExplanationCards() {
    final items = (_reviewData?['explanations'] as List<dynamic>? ?? []);
    if (items.isEmpty) {
      return [
        const AppEmptyState(
          icon: Icons.fact_check_outlined,
          title: 'No mistakes to explain',
          description:
              'This attempt does not have stored incorrect answers for the AI tutor to review.',
        ),
      ];
    }

    return items.map((item) {
      final explanation = item as Map<String, dynamic>;
      return Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: AppSurface(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                explanation['question']?.toString() ?? 'Question',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 12),
              AppStatusBanner(
                message: 'Your answer: ${explanation['your_answer']}',
                color: EduQuestColors.danger,
                icon: Icons.close,
              ),
              const SizedBox(height: 10),
              AppStatusBanner(
                message: 'Correct answer: ${explanation['correct_answer']}',
                color: EduQuestColors.success,
                icon: Icons.check,
              ),
              const SizedBox(height: 12),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: EduQuestColors.bg,
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: EduQuestColors.border),
                ),
                child: Text(
                  explanation['explanation']?.toString() ?? '',
                  style: Theme.of(
                    context,
                  ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
                ),
              ),
              const SizedBox(height: 12),
              Text(
                explanation['why_your_answer_was_wrong']?.toString() ?? '',
                style: Theme.of(
                  context,
                ).textTheme.bodySmall?.copyWith(color: Colors.white70),
              ),
              const SizedBox(height: 8),
              Text(
                explanation['why_correct_answer_is_correct']?.toString() ?? '',
                style: Theme.of(
                  context,
                ).textTheme.bodySmall?.copyWith(color: EduQuestColors.success),
              ),
              const SizedBox(height: 10),
              Text(
                'Lesson connection: ${explanation['lesson_connection'] ?? ''}',
                style: Theme.of(
                  context,
                ).textTheme.bodySmall?.copyWith(color: EduQuestColors.info),
              ),
            ],
          ),
        ),
      );
    }).toList();
  }

  Widget _buildMessageBubble(Map<String, String> message) {
    final isUser = message['role'] == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.8,
        ),
        decoration: BoxDecoration(
          color: isUser ? EduQuestColors.primary : EduQuestColors.surface,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(18),
            topRight: const Radius.circular(18),
            bottomLeft: isUser ? const Radius.circular(18) : Radius.zero,
            bottomRight: isUser ? Radius.zero : const Radius.circular(18),
          ),
        ),
        child: Text(
          message['text'] ?? '',
          style: const TextStyle(fontSize: 15, height: 1.45),
        ),
      ),
    );
  }

  Widget _buildTypingIndicator() {
    return const Padding(
      padding: EdgeInsets.only(bottom: 12),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Text(
          'AI Teacher is thinking...',
          style: TextStyle(color: EduQuestColors.textMuted),
        ),
      ),
    );
  }

  Widget _buildComposer() {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
        decoration: const BoxDecoration(
          color: EduQuestColors.bgElevated,
          border: Border(top: BorderSide(color: EduQuestColors.border)),
        ),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final stacked = constraints.maxWidth < 360;
            final field = TextField(
              controller: _questionController,
              minLines: 1,
              maxLines: 4,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => _sendQuestion(),
              decoration: const InputDecoration(
                hintText: 'Ask why the correct answer works...',
              ),
            );

            final button = SizedBox(
              width: stacked ? double.infinity : 56,
              height: 56,
              child: ElevatedButton(
                onPressed: (_isTyping || _sessionId == null) ? null : _sendQuestion,
                style: ElevatedButton.styleFrom(
                  backgroundColor: EduQuestColors.info,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(18),
                  ),
                  padding: EdgeInsets.zero,
                ),
                child:
                    stacked
                        ? const Text('Send question')
                        : const Icon(Icons.send),
              ),
            );

            if (stacked) {
              return Column(
                children: [field, const SizedBox(height: 10), button],
              );
            }

            return Row(
              children: [
                Expanded(child: field),
                const SizedBox(width: 10),
                button,
              ],
            );
          },
        ),
      ),
    );
  }
}
