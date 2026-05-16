import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../ui/app_components.dart';
import '../ui/eduquest_theme.dart';
import 'admin_screen.dart';
import 'dashboard_screen.dart';
import 'teacher_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _fullNameCtl = TextEditingController();
  final _emailCtl = TextEditingController(text: 'student@eduquest.com');
  final _pwdCtl = TextEditingController();
  final _confirmPwdCtl = TextEditingController();

  bool _isLoading = false;
  bool _isRegisterMode = false;
  String _error = '';
  String _success = '';

  static const _demoAccounts = [
    (
      label: 'Student demo',
      email: 'student@eduquest.com',
      role: 'Student',
    ),
    (
      label: 'Teacher demo',
      email: 'teacher@eduquest.com',
      role: 'Teacher',
    ),
    (
      label: 'Admin demo',
      email: 'admin@eduquest.com',
      role: 'Admin',
    ),
  ];

  Future<void> _login() async {
    setState(() {
      _isLoading = true;
      _error = '';
      _success = '';
    });

    final res = await ApiService.login(_emailCtl.text.trim(), _pwdCtl.text);
    if (!mounted) return;

    if (res != null) {
      final userIdValue = res['user_id'] ?? res['id'];
      final userId = userIdValue is num ? userIdValue.toInt() : null;
      if (userId == null) {
        setState(() {
          _isLoading = false;
          _error = 'The server returned an invalid user profile payload.';
        });
        return;
      }
      final role = res['role'];
      Widget nextScreen;
      if (role == 'teacher') {
        nextScreen = TeacherScreen(userId: userId);
      } else if (role == 'admin') {
        nextScreen = AdminScreen(userId: userId);
      } else {
        nextScreen = DashboardScreen(userId: userId);
      }
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => nextScreen),
      );
      return;
    }

    setState(() {
      _isLoading = false;
      _error =
          'We could not sign you in. Check the server connection or verify your credentials.';
    });
  }

  Future<void> _register() async {
    final fullName = _fullNameCtl.text.trim();
    final email = _emailCtl.text.trim();
    final password = _pwdCtl.text;
    final confirmPassword = _confirmPwdCtl.text;

    if (fullName.isEmpty || email.isEmpty || password.isEmpty) {
      setState(
        () => _error = 'Fill in your full name, email, and password first.',
      );
      return;
    }
    if (password.length < 6) {
      setState(() => _error = 'Password must contain at least 6 characters.');
      return;
    }
    if (password != confirmPassword) {
      setState(() => _error = 'Password confirmation does not match.');
      return;
    }

    setState(() {
      _isLoading = true;
      _error = '';
      _success = '';
    });

    final result = await ApiService.register(fullName, email, password);
    if (!mounted) return;

    if (result == null) {
      setState(() {
        _isLoading = false;
        _error = 'Registration failed. This email may already be in use.';
      });
      return;
    }

    _confirmPwdCtl.clear();
    setState(() {
      _isRegisterMode = false;
      _isLoading = false;
      _success = 'Account created. Signing you in...';
    });

    await _login();
  }

  void _toggleMode(bool register) {
    setState(() {
      _isRegisterMode = register;
      _error = '';
      _success = '';
      if (!_isRegisterMode) {
        _confirmPwdCtl.clear();
      }
    });
  }

  void _prefillDemo(String email) {
    setState(() {
      _emailCtl.text = email;
      _pwdCtl.clear();
      _isRegisterMode = false;
      _error = '';
      _success = 'Demo email selected. Enter the Firebase Auth password to continue.';
    });
  }

  @override
  void dispose() {
    _fullNameCtl.dispose();
    _emailCtl.dispose();
    _pwdCtl.dispose();
    _confirmPwdCtl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF07131F), Color(0xFF0C1C2F), Color(0xFF13283E)],
        ),
      ),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 480),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _buildHero(context),
                    const SizedBox(height: 20),
                    _buildAuthCard(context),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHero(BuildContext context) {
    return AppSurface(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(18),
                  gradient: const LinearGradient(
                    colors: [EduQuestColors.primary, EduQuestColors.secondary],
                  ),
                ),
                child: const Icon(Icons.auto_stories, color: Colors.white),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'EduQuest',
                      style: Theme.of(context).textTheme.headlineMedium,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'AI-enhanced game-based learning for students, teachers, and administrators.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 22),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: const [
              AppInfoChip(
                label: 'Immediate feedback',
                color: EduQuestColors.primary,
                icon: Icons.bolt,
              ),
              AppInfoChip(
                label: 'Retry-friendly practice',
                color: EduQuestColors.secondary,
                icon: Icons.loop,
              ),
              AppInfoChip(
                label: 'Teacher analytics',
                color: EduQuestColors.info,
                icon: Icons.insights,
              ),
            ],
          ),
          const SizedBox(height: 18),
          Text(
            'Built to demonstrate a mobile-first thesis MVP with course paths, adaptive practice, AI explanations, and role-aware dashboards.',
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
          ),
        ],
      ),
    );
  }

  Widget _buildAuthCard(BuildContext context) {
    return AppSurface(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: EduQuestColors.bg,
              borderRadius: BorderRadius.circular(18),
            ),
            child: Row(
              children: [
                Expanded(
                  child: _buildModeButton(
                    'Sign in',
                    !_isRegisterMode,
                    () => _toggleMode(false),
                  ),
                ),
                Expanded(
                  child: _buildModeButton(
                    'Create account',
                    _isRegisterMode,
                    () => _toggleMode(true),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 22),
          Text(
            _isRegisterMode
                ? 'Create your learner account'
                : 'Sign in to continue',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 6),
          Text(
            _isRegisterMode
                ? 'New registrations are created as student accounts by default.'
                : 'Use a demo account or sign in with your existing account.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 20),
          if (_isRegisterMode) ...[
            TextField(
              controller: _fullNameCtl,
              decoration: const InputDecoration(
                labelText: 'Full name',
                prefixIcon: Icon(Icons.person_outline),
              ),
            ),
            const SizedBox(height: 14),
          ],
          TextField(
            controller: _emailCtl,
            keyboardType: TextInputType.emailAddress,
            decoration: const InputDecoration(
              labelText: 'Email',
              prefixIcon: Icon(Icons.alternate_email),
            ),
          ),
          const SizedBox(height: 14),
          TextField(
            controller: _pwdCtl,
            obscureText: true,
            decoration: const InputDecoration(
              labelText: 'Password',
              prefixIcon: Icon(Icons.lock_outline),
            ),
          ),
          if (_isRegisterMode) ...[
            const SizedBox(height: 14),
            TextField(
              controller: _confirmPwdCtl,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'Confirm password',
                prefixIcon: Icon(Icons.verified_user_outlined),
              ),
            ),
          ],
          if (_error.isNotEmpty) ...[
            const SizedBox(height: 16),
            AppStatusBanner(
              message: _error,
              color: EduQuestColors.danger,
              icon: Icons.error_outline,
            ),
          ],
          if (_success.isNotEmpty) ...[
            const SizedBox(height: 16),
            AppStatusBanner(
              message: _success,
              color: EduQuestColors.success,
              icon: Icons.check_circle_outline,
            ),
          ],
          const SizedBox(height: 18),
          ElevatedButton(
            onPressed:
                _isLoading ? null : (_isRegisterMode ? _register : _login),
            child:
                _isLoading
                    ? const SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(
                        strokeWidth: 2.5,
                        color: Colors.white,
                      ),
                    )
                    : Text(
                      _isRegisterMode
                          ? 'Create account and continue'
                          : 'Sign in to EduQuest',
                    ),
          ),
          const SizedBox(height: 18),
          Text(
            'Quick demo access',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 10),
          ..._demoAccounts.map(
            (account) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: OutlinedButton(
                onPressed: () => _prefillDemo(account.email),
                child: Row(
                  children: [
                    Icon(
                      account.role == 'Teacher'
                          ? Icons.school_outlined
                          : account.role == 'Admin'
                          ? Icons.admin_panel_settings_outlined
                          : Icons.person_outline,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text('${account.label} • ${account.email}'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildModeButton(String label, bool selected, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 160),
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: selected ? EduQuestColors.surfaceAlt : Colors.transparent,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Text(
          label,
          textAlign: TextAlign.center,
          style: TextStyle(
            fontWeight: FontWeight.w700,
            color: selected ? Colors.white : EduQuestColors.textMuted,
          ),
        ),
      ),
    );
  }
}
